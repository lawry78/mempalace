"""
deep_dive.py — Topic deep-dive export for MemPalace.

Exhaustively collects everything the palace knows about a topic using
three strategies:

  1. Semantic search — ChromaDB vector similarity (high n_results)
  2. Knowledge graph — entity relationships and timeline
  3. Room scan — drawers from rooms whose name matches the topic

Results are deduplicated, grouped by wing/room, and formatted as
structured Markdown.

Usage:
    from mempalace.deep_dive import deep_dive
    md = deep_dive("authentication", palace_path="/path/to/palace")
    # or with file output:
    md = deep_dive("authentication", output_path="auth_report.md")
"""

import os
from datetime import datetime
from pathlib import Path

import chromadb
from chromadb.errors import ChromaError, InvalidCollectionException

from .config import MempalaceConfig, DEFAULT_COLLECTION_NAME
from .collection_utils import fetch_all
from .knowledge_graph import KnowledgeGraph


def deep_dive(
    topic: str,
    palace_path: str = None,
    wing: str = None,
    output_path: str = None,
    similarity_threshold: float = 0.3,
    max_semantic: int = 100,
    kg_db_path: str = None,
) -> dict:
    """
    Exhaustive topic export — collects everything the palace knows.

    Args:
        topic: The topic to search for.
        palace_path: Path to the ChromaDB palace. Defaults to config.
        wing: Optional wing filter to narrow scope.
        output_path: If given, writes the markdown to this file.
        similarity_threshold: Minimum similarity to include (0.0-1.0).
        max_semantic: Max results from semantic search.
        kg_db_path: Path to knowledge graph SQLite. Defaults to config.

    Returns:
        dict with keys: "markdown", "stats", "output_path" (if written).
    """
    cfg = MempalaceConfig()
    palace_path = palace_path or cfg.palace_path

    # Connect to palace
    try:
        client = chromadb.PersistentClient(path=palace_path)
        col = client.get_collection(DEFAULT_COLLECTION_NAME)
    except (InvalidCollectionException, ValueError):
        return {
            "error": "No palace found",
            "hint": "Run: mempalace init <dir> && mempalace mine <dir>",
        }

    # ── Strategy 1: Semantic search ──────────────────────────────────
    drawers = {}  # id → {text, wing, room, source_file, similarity, strategy}

    where = {"wing": wing} if wing else None
    try:
        kwargs = {
            "query_texts": [topic],
            "n_results": max_semantic,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        results = col.query(**kwargs)

        for doc_id, doc, meta, dist in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            similarity = round(1 - dist, 3)
            if similarity >= similarity_threshold:
                drawers[doc_id] = {
                    "text": doc,
                    "wing": meta.get("wing", "unknown"),
                    "room": meta.get("room", "unknown"),
                    "source_file": Path(meta.get("source_file", "?")).name,
                    "date": meta.get("date", meta.get("filed_at", "")),
                    "similarity": similarity,
                    "strategy": "semantic",
                }
    except ChromaError:
        pass

    # ── Strategy 2: Room name matching ───────────────────────────────
    # Find rooms whose name contains the topic keywords
    topic_words = [w.lower() for w in topic.split() if len(w) > 2]
    if topic_words:
        all_result = fetch_all(col, include=["metadatas"], where=where)
        matching_rooms = set()
        for meta in all_result["metadatas"]:
            room = meta.get("room", "")
            if any(word in room.lower() for word in topic_words):
                matching_rooms.add(room)

        # Fetch full content from matching rooms
        for room_name in matching_rooms:
            room_where = {"room": room_name}
            if wing:
                room_where = {"$and": [{"wing": wing}, {"room": room_name}]}
            room_result = fetch_all(
                col, include=["documents", "metadatas"], where=room_where
            )
            for rid, doc, meta in zip(
                room_result["ids"],
                room_result["documents"],
                room_result["metadatas"],
            ):
                if rid not in drawers:
                    drawers[rid] = {
                        "text": doc,
                        "wing": meta.get("wing", "unknown"),
                        "room": meta.get("room", "unknown"),
                        "source_file": Path(meta.get("source_file", "?")).name,
                        "date": meta.get("date", meta.get("filed_at", "")),
                        "similarity": None,
                        "strategy": "room_match",
                    }

    # ── Strategy 3: Knowledge Graph ──────────────────────────────────
    kg_facts = []
    try:
        kg = KnowledgeGraph(db_path=kg_db_path) if kg_db_path else KnowledgeGraph()
        # Try topic as entity name
        facts = kg.query_entity(topic, direction="both")
        if facts:
            kg_facts.extend(facts)
        # Also try individual words as entities
        for word in topic.split():
            if len(word) > 2 and word.lower() != topic.lower():
                word_facts = kg.query_entity(word, direction="both")
                for fact in word_facts:
                    if fact not in kg_facts:
                        kg_facts.append(fact)
    except Exception:
        pass  # KG is optional — don't fail if unavailable

    # ── Build Markdown ───────────────────────────────────────────────
    md = _format_markdown(topic, drawers, kg_facts, wing)

    stats = {
        "topic": topic,
        "total_drawers": len(drawers),
        "semantic_hits": sum(1 for d in drawers.values() if d["strategy"] == "semantic"),
        "room_match_hits": sum(1 for d in drawers.values() if d["strategy"] == "room_match"),
        "kg_facts": len(kg_facts),
        "wings": list({d["wing"] for d in drawers.values()}),
        "rooms": list({d["room"] for d in drawers.values()}),
    }

    result = {"markdown": md, "stats": stats}

    if output_path:
        output_path = os.path.expanduser(output_path)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md)
        result["output_path"] = output_path

    return result


def _format_markdown(topic, drawers, kg_facts, wing_filter):
    """Format collected data as structured Markdown."""
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append(f"# Deep Dive: {topic}")
    lines.append("")
    lines.append(f"*Generated {now} by MemPalace*")
    if wing_filter:
        lines.append(f"*Filtered to wing: {wing_filter}*")
    lines.append(f"*{len(drawers)} drawers collected, {len(kg_facts)} knowledge graph facts*")
    lines.append("")

    # ── Knowledge Graph section ──────────────────────────────────────
    if kg_facts:
        lines.append("## Knowledge Graph")
        lines.append("")
        current = [f for f in kg_facts if f.get("current")]
        expired = [f for f in kg_facts if not f.get("current")]

        if current:
            lines.append("### Current Facts")
            lines.append("")
            for f in current:
                since = f" (since {f['valid_from']})" if f.get("valid_from") else ""
                lines.append(f"- **{f['subject']}** {f['predicate']} **{f['object']}**{since}")
            lines.append("")

        if expired:
            lines.append("### Historical Facts")
            lines.append("")
            for f in expired:
                period = ""
                if f.get("valid_from") and f.get("valid_to"):
                    period = f" ({f['valid_from']} → {f['valid_to']})"
                lines.append(f"- ~~{f['subject']} {f['predicate']} {f['object']}~~{period}")
            lines.append("")

    # ── Drawers grouped by wing/room ─────────────────────────────────
    if drawers:
        lines.append("## Memories")
        lines.append("")

        # Group by wing → room
        grouped = {}
        for d in drawers.values():
            key = (d["wing"], d["room"])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(d)

        # Sort: wing alphabetically, room alphabetically
        for (wing_name, room_name) in sorted(grouped.keys()):
            entries = grouped[(wing_name, room_name)]
            # Sort entries: semantic first (by similarity desc), then room_match
            entries.sort(
                key=lambda e: (0 if e["strategy"] == "semantic" else 1, -(e["similarity"] or 0)),
            )

            lines.append(f"### {wing_name} / {room_name}")
            lines.append("")

            for entry in entries:
                source = entry["source_file"]
                date = entry["date"][:10] if entry["date"] else ""
                sim = f" (sim: {entry['similarity']})" if entry["similarity"] else " (room match)"
                header_parts = []
                if source and source != "?":
                    header_parts.append(source)
                if date:
                    header_parts.append(date)
                header = " — ".join(header_parts)

                lines.append(f"**{header}**{sim}")
                lines.append("")
                # Indent the content
                for text_line in entry["text"].strip().split("\n"):
                    lines.append(f"> {text_line}")
                lines.append("")
    else:
        lines.append("## No Results")
        lines.append("")
        lines.append(f"No drawers found related to **{topic}**.")
        lines.append("")

    lines.append("---")
    lines.append(f"*End of deep dive for: {topic}*")

    return "\n".join(lines)
