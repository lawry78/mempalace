"""
doctor.py — Palace health check, conflict detection, and smart merge.

Diagnoses problems in the palace and optionally fixes them:
  - Orphan drawers (missing wing/room metadata)
  - Near-duplicate drawers (similarity > threshold)
  - Tiny rooms (1-2 drawers that could be merged)
  - Stale KG facts (old active triples without valid_to)
  - Conflicts (contradictory information across drawers or KG)

Usage:
    from mempalace.doctor import diagnose
    report = diagnose(palace_path="/path/to/palace")
"""

import hashlib
from collections import defaultdict
from datetime import datetime

import chromadb
from chromadb.errors import ChromaError, InvalidCollectionException

from .config import MempalaceConfig, DEFAULT_COLLECTION_NAME
from .collection_utils import fetch_all
from .knowledge_graph import KnowledgeGraph


def diagnose(palace_path=None, wing=None, kg_db_path=None, duplicate_threshold=0.95):
    """Run all health checks and return a structured report.

    Args:
        palace_path: Path to ChromaDB palace.
        wing: Optional wing filter.
        kg_db_path: Path to KG SQLite.
        duplicate_threshold: Similarity threshold for duplicate detection (0.0-1.0).

    Returns:
        dict with "checks" list, "summary", and "healthy" bool.
    """
    cfg = MempalaceConfig()
    palace_path = palace_path or cfg.palace_path

    try:
        client = chromadb.PersistentClient(path=palace_path)
        col = client.get_collection(DEFAULT_COLLECTION_NAME)
    except (InvalidCollectionException, ValueError):
        return {"error": "No palace found", "healthy": False, "checks": [], "summary": {}}

    where = {"wing": wing} if wing else None
    result = fetch_all(col, include=["documents", "metadatas"], where=where)

    checks = []
    checks.append(check_orphans(result))
    checks.append(check_duplicates(col, result, threshold=duplicate_threshold))
    checks.append(check_tiny_rooms(result))
    checks.append(check_conflicts(col, result))

    # KG checks
    try:
        kg = KnowledgeGraph(db_path=kg_db_path) if kg_db_path else KnowledgeGraph()
        checks.append(check_stale_kg(kg))
        checks.append(check_kg_conflicts(kg))
    except Exception:
        pass

    total_issues = sum(len(c.get("issues", [])) for c in checks)
    summary = {
        "total_drawers": len(result["ids"]),
        "total_issues": total_issues,
        "critical": sum(1 for c in checks for i in c.get("issues", []) if i.get("severity") == "critical"),
        "warning": sum(1 for c in checks for i in c.get("issues", []) if i.get("severity") == "warning"),
        "info": sum(1 for c in checks for i in c.get("issues", []) if i.get("severity") == "info"),
    }

    return {
        "healthy": total_issues == 0,
        "summary": summary,
        "checks": checks,
    }


# ── Check: Orphan drawers ────────────────────────────────────────────


def check_orphans(result):
    """Find drawers with missing or empty wing/room metadata."""
    issues = []
    for drawer_id, meta in zip(result["ids"], result["metadatas"]):
        missing = []
        if not meta.get("wing"):
            missing.append("wing")
        if not meta.get("room"):
            missing.append("room")
        if missing:
            issues.append({
                "severity": "warning",
                "drawer_id": drawer_id,
                "message": f"Missing metadata: {', '.join(missing)}",
            })
    return {"check": "orphans", "description": "Drawers with missing wing/room metadata", "issues": issues}


# ── Check: Near-duplicates ───────────────────────────────────────────


def check_duplicates(col, result, threshold=0.95):
    """Find near-duplicate drawer pairs using semantic similarity."""
    issues = []
    seen = set()

    # Sample drawers to query against (limit to avoid O(n²) on large palaces)
    sample_ids = result["ids"][:200]
    sample_docs = result["documents"][:200]
    sample_metas = result["metadatas"][:200]

    for i, (doc, meta, doc_id) in enumerate(zip(sample_docs, sample_metas, sample_ids)):
        if doc_id in seen:
            continue
        try:
            hits = col.query(
                query_texts=[doc],
                n_results=5,
                include=["metadatas", "distances"],
            )
        except ChromaError:
            continue

        for j, (hit_id, dist) in enumerate(zip(hits["ids"][0], hits["distances"][0])):
            if hit_id == doc_id:
                continue
            similarity = round(1 - dist, 3)
            pair_key = tuple(sorted([doc_id, hit_id]))
            if similarity >= threshold and pair_key not in seen:
                seen.add(pair_key)
                hit_meta = hits["metadatas"][0][j]
                issues.append({
                    "severity": "info",
                    "drawer_a": doc_id,
                    "drawer_b": hit_id,
                    "similarity": similarity,
                    "message": f"Near-duplicate ({similarity}): "
                               f"{meta.get('wing', '?')}/{meta.get('room', '?')} ↔ "
                               f"{hit_meta.get('wing', '?')}/{hit_meta.get('room', '?')}",
                })

    return {"check": "duplicates", "description": "Near-duplicate drawer pairs", "issues": issues}


# ── Check: Tiny rooms ────────────────────────────────────────────────


def check_tiny_rooms(result):
    """Find rooms with very few drawers that might be merge candidates."""
    room_counts = defaultdict(int)
    for meta in result["metadatas"]:
        room = meta.get("room", "")
        if room:
            room_counts[room] += 1

    issues = []
    for room, count in sorted(room_counts.items()):
        if count <= 2 and room not in ("general", "diary"):
            issues.append({
                "severity": "info",
                "room": room,
                "count": count,
                "message": f"Room '{room}' has only {count} drawer(s) — consider merging into a related room",
            })
    return {"check": "tiny_rooms", "description": "Rooms with very few drawers", "issues": issues}


# ── Check: Conflicts between drawers ─────────────────────────────────


def check_conflicts(col, result):
    """Detect potential contradictions between drawers.

    Strategy: find drawer pairs that are semantically similar (same topic)
    but from different time periods — the newer one may contradict the older.
    Focus on drawers containing decision/change language.
    """
    issues = []
    CHANGE_MARKERS = [
        "switched", "migrated", "replaced", "changed", "moved", "upgraded",
        "downgraded", "deprecated", "removed", "dropped", "instead of",
        "no longer", "used to", "previously", "now we use", "decided to",
    ]

    # Find drawers with change language
    change_drawers = []
    for doc_id, doc, meta in zip(result["ids"], result["documents"], result["metadatas"]):
        doc_lower = doc.lower()
        markers_found = [m for m in CHANGE_MARKERS if m in doc_lower]
        if markers_found:
            change_drawers.append({
                "id": doc_id,
                "doc": doc,
                "meta": meta,
                "markers": markers_found,
                "date": meta.get("date", meta.get("filed_at", "")),
            })

    # For each change drawer, find semantically similar older drawers
    for cd in change_drawers[:50]:  # cap to avoid slow scans
        try:
            hits = col.query(
                query_texts=[cd["doc"]],
                n_results=10,
                include=["documents", "metadatas", "distances"],
            )
        except ChromaError:
            continue

        for hit_id, hit_doc, hit_meta, dist in zip(
            hits["ids"][0], hits["documents"][0], hits["metadatas"][0], hits["distances"][0]
        ):
            if hit_id == cd["id"]:
                continue
            similarity = round(1 - dist, 3)
            if similarity < 0.5:
                continue

            hit_date = hit_meta.get("date", hit_meta.get("filed_at", ""))
            # If both have dates and the hit is older, it might be outdated
            if cd["date"] and hit_date and hit_date < cd["date"]:
                # Check if the hit doesn't have change markers (it's the "old" state)
                hit_lower = hit_doc.lower()
                hit_has_changes = any(m in hit_lower for m in CHANGE_MARKERS)
                if not hit_has_changes:
                    issues.append({
                        "severity": "critical",
                        "newer_id": cd["id"],
                        "older_id": hit_id,
                        "similarity": similarity,
                        "newer_date": cd["date"],
                        "older_date": hit_date,
                        "change_markers": cd["markers"][:3],
                        "newer_preview": cd["doc"][:120],
                        "older_preview": hit_doc[:120],
                        "message": f"Potential conflict: '{cd['doc'][:60]}...' ({cd['date']}) "
                                   f"may contradict '{hit_doc[:60]}...' ({hit_date})",
                    })
                    break  # one conflict per change drawer is enough

    return {"check": "conflicts", "description": "Contradictory information between drawers", "issues": issues}


# ── Check: Stale KG facts ────────────────────────────────────────────


def check_stale_kg(kg, stale_days=365):
    """Find KG triples that are old and still active (no valid_to)."""
    issues = []
    try:
        timeline = kg.timeline()
    except Exception:
        return {"check": "stale_kg", "description": "Old KG facts without expiry", "issues": []}

    now = datetime.now().strftime("%Y-%m-%d")
    for fact in timeline:
        if not fact.get("current"):
            continue
        valid_from = fact.get("valid_from", "")
        if not valid_from:
            continue
        try:
            days_old = (datetime.strptime(now, "%Y-%m-%d") - datetime.strptime(valid_from, "%Y-%m-%d")).days
        except ValueError:
            continue
        if days_old > stale_days:
            issues.append({
                "severity": "info",
                "subject": fact["subject"],
                "predicate": fact["predicate"],
                "object": fact["object"],
                "valid_from": valid_from,
                "days_old": days_old,
                "message": f"'{fact['subject']} {fact['predicate']} {fact['object']}' "
                           f"active since {valid_from} ({days_old} days) — still current?",
            })
    return {"check": "stale_kg", "description": "Old KG facts without expiry", "issues": issues}


# ── Check: KG contradictions ─────────────────────────────────────────


def check_kg_conflicts(kg):
    """Find KG triples that contradict each other.

    Looks for: same subject + same predicate with different objects, both active.
    E.g. "Alice works_at Acme" AND "Alice works_at NewCo" both current.
    """
    issues = []
    try:
        timeline = kg.timeline()
    except Exception:
        return {"check": "kg_conflicts", "description": "Contradictory active KG facts", "issues": []}

    # Group active facts by (subject, predicate)
    active = defaultdict(list)
    for fact in timeline:
        if fact.get("current"):
            key = (fact["subject"], fact["predicate"])
            active[key].append(fact)

    for (subj, pred), facts in active.items():
        if len(facts) > 1:
            objects = [f["object"] for f in facts]
            # Some predicates naturally have multiple values (e.g. "does", "likes")
            # Flag only typically-unique predicates
            unique_preds = {"works_at", "lives_in", "married_to", "reports_to", "managed_by", "uses", "runs_on"}
            if pred in unique_preds:
                issues.append({
                    "severity": "critical",
                    "subject": subj,
                    "predicate": pred,
                    "objects": objects,
                    "message": f"Conflicting: '{subj} {pred}' has multiple active values: {', '.join(objects)}",
                })
            elif len(facts) > 3:
                issues.append({
                    "severity": "warning",
                    "subject": subj,
                    "predicate": pred,
                    "objects": objects,
                    "message": f"'{subj} {pred}' has {len(facts)} active values — review for accuracy",
                })

    return {"check": "kg_conflicts", "description": "Contradictory active KG facts", "issues": issues}


# ── Smart Merge ──────────────────────────────────────────────────────


def merge_drawers(palace_path, drawer_id_keep, drawer_id_remove):
    """Remove a duplicate drawer, keeping the other.

    Returns dict with success status.
    """
    cfg = MempalaceConfig()
    palace_path = palace_path or cfg.palace_path

    try:
        client = chromadb.PersistentClient(path=palace_path)
        col = client.get_collection(DEFAULT_COLLECTION_NAME)
    except (InvalidCollectionException, ValueError):
        return {"success": False, "error": "No palace found"}

    # Verify both exist
    keep = col.get(ids=[drawer_id_keep])
    remove = col.get(ids=[drawer_id_remove])
    if not keep["ids"]:
        return {"success": False, "error": f"Drawer to keep not found: {drawer_id_keep}"}
    if not remove["ids"]:
        return {"success": False, "error": f"Drawer to remove not found: {drawer_id_remove}"}

    try:
        col.delete(ids=[drawer_id_remove])
        return {
            "success": True,
            "kept": drawer_id_keep,
            "removed": drawer_id_remove,
        }
    except ChromaError as e:
        return {"success": False, "error": str(e)}
