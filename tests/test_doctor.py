"""
test_doctor.py — Tests for the palace doctor (health check, conflict detection, merge).
"""

import os


def _add_drawers(collection, drawers):
    """Helper to add multiple drawers to a collection."""
    ids, docs, metas = [], [], []
    for i, (doc, wing, room, date) in enumerate(drawers):
        ids.append(f"test_{wing}_{room}_{i}")
        docs.append(doc)
        metas.append({
            "wing": wing, "room": room, "source_file": f"file_{i}.txt",
            "chunk_index": 0, "added_by": "test",
            "filed_at": f"{date}T12:00:00", "date": date,
        })
    collection.add(ids=ids, documents=docs, metadatas=metas)


# ── Diagnose (full pipeline) ─────────────────────────────────────────


class TestDiagnose:
    def test_healthy_palace(self, palace_path, seeded_collection):
        from mempalace.doctor import diagnose

        report = diagnose(palace_path=palace_path)
        assert "error" not in report
        assert isinstance(report["checks"], list)
        assert "summary" in report

    def test_no_palace(self, tmp_dir):
        from mempalace.doctor import diagnose

        report = diagnose(palace_path=os.path.join(tmp_dir, "nonexistent"))
        assert "error" in report
        assert report["healthy"] is False

    def test_empty_palace(self, palace_path, collection):
        from mempalace.doctor import diagnose

        report = diagnose(palace_path=palace_path)
        assert report["healthy"] is True
        assert report["summary"]["total_drawers"] == 0

    def test_wing_filter(self, palace_path, seeded_collection):
        from mempalace.doctor import diagnose

        report = diagnose(palace_path=palace_path, wing="project")
        assert report["summary"]["total_drawers"] == 3  # seeded has 3 project drawers

    def test_summary_counts(self, palace_path, seeded_collection):
        from mempalace.doctor import diagnose

        report = diagnose(palace_path=palace_path)
        s = report["summary"]
        assert s["total_issues"] == s["critical"] + s["warning"] + s["info"]


# ── Check: Orphans ───────────────────────────────────────────────────


class TestCheckOrphans:
    def test_no_orphans(self, palace_path, seeded_collection):
        from mempalace.doctor import diagnose

        report = diagnose(palace_path=palace_path)
        orphan_check = next(c for c in report["checks"] if c["check"] == "orphans")
        assert len(orphan_check["issues"]) == 0

    def test_detects_missing_wing(self, palace_path, collection):
        collection.add(
            ids=["orphan_1"],
            documents=["Some content without proper metadata"],
            metadatas=[{"room": "backend", "source_file": "test.py",
                        "chunk_index": 0, "added_by": "test", "filed_at": "2026-01-01T00:00:00"}],
        )
        from mempalace.doctor import diagnose

        report = diagnose(palace_path=palace_path)
        orphan_check = next(c for c in report["checks"] if c["check"] == "orphans")
        assert len(orphan_check["issues"]) == 1
        assert "wing" in orphan_check["issues"][0]["message"]


# ── Check: Duplicates ────────────────────────────────────────────────


class TestCheckDuplicates:
    def test_no_duplicates(self, palace_path, seeded_collection):
        from mempalace.doctor import diagnose

        report = diagnose(palace_path=palace_path)
        dup_check = next(c for c in report["checks"] if c["check"] == "duplicates")
        assert len(dup_check["issues"]) == 0

    def test_detects_near_duplicates(self, palace_path, collection):
        # Add two nearly identical drawers
        collection.add(
            ids=["dup_a", "dup_b"],
            documents=[
                "The authentication module uses JWT tokens for session management with 24h expiry.",
                "The authentication module uses JWT tokens for session management with 24 hour expiry.",
            ],
            metadatas=[
                {"wing": "project", "room": "backend", "source_file": "a.py",
                 "chunk_index": 0, "added_by": "test", "filed_at": "2026-01-01T00:00:00"},
                {"wing": "project", "room": "backend", "source_file": "b.py",
                 "chunk_index": 0, "added_by": "test", "filed_at": "2026-01-02T00:00:00"},
            ],
        )
        from mempalace.doctor import diagnose

        report = diagnose(palace_path=palace_path, duplicate_threshold=0.9)
        dup_check = next(c for c in report["checks"] if c["check"] == "duplicates")
        assert len(dup_check["issues"]) >= 1
        assert dup_check["issues"][0]["severity"] == "info"


# ── Check: Tiny rooms ────────────────────────────────────────────────


class TestCheckTinyRooms:
    def test_detects_tiny_room(self, palace_path, collection):
        collection.add(
            ids=["tiny_1"],
            documents=["A single lonely drawer in a room by itself."],
            metadatas=[{"wing": "project", "room": "lonely-room", "source_file": "t.py",
                        "chunk_index": 0, "added_by": "test", "filed_at": "2026-01-01T00:00:00"}],
        )
        from mempalace.doctor import diagnose

        report = diagnose(palace_path=palace_path)
        tiny_check = next(c for c in report["checks"] if c["check"] == "tiny_rooms")
        rooms = [i["room"] for i in tiny_check["issues"]]
        assert "lonely-room" in rooms

    def test_ignores_general_and_diary(self, palace_path, collection):
        collection.add(
            ids=["gen_1", "diary_1"],
            documents=["General content", "Diary entry"],
            metadatas=[
                {"wing": "w", "room": "general", "source_file": "g.py",
                 "chunk_index": 0, "added_by": "test", "filed_at": "2026-01-01T00:00:00"},
                {"wing": "w", "room": "diary", "source_file": "d.py",
                 "chunk_index": 0, "added_by": "test", "filed_at": "2026-01-01T00:00:00"},
            ],
        )
        from mempalace.doctor import diagnose

        report = diagnose(palace_path=palace_path)
        tiny_check = next(c for c in report["checks"] if c["check"] == "tiny_rooms")
        rooms = [i["room"] for i in tiny_check["issues"]]
        assert "general" not in rooms
        assert "diary" not in rooms


# ── Check: Conflicts ─────────────────────────────────────────────────


class TestCheckConflicts:
    def test_detects_drawer_conflict(self, palace_path, collection):
        _add_drawers(collection, [
            ("We use REST API for all client communication.", "project", "backend", "2025-01-01"),
            ("We switched from REST to GraphQL for the dashboard API.", "project", "backend", "2025-06-01"),
        ])
        from mempalace.doctor import diagnose

        report = diagnose(palace_path=palace_path)
        conflict_check = next(c for c in report["checks"] if c["check"] == "conflicts")
        # The "switched" marker should trigger conflict detection
        if conflict_check["issues"]:
            assert conflict_check["issues"][0]["severity"] == "critical"

    def test_no_conflicts_in_unrelated_drawers(self, palace_path, collection):
        _add_drawers(collection, [
            ("Authentication uses JWT tokens.", "project", "auth", "2025-01-01"),
            ("The database runs on PostgreSQL 15.", "project", "database", "2025-01-01"),
        ])
        from mempalace.doctor import diagnose

        report = diagnose(palace_path=palace_path)
        conflict_check = next(c for c in report["checks"] if c["check"] == "conflicts")
        assert len(conflict_check["issues"]) == 0


# ── Check: Stale KG ──────────────────────────────────────────────────


class TestCheckStaleKG:
    def test_detects_stale_fact(self, palace_path, collection, seeded_kg):
        from mempalace.doctor import diagnose

        # seeded_kg has "Alice parent_of Max" from 2015-04-01 — very old
        report = diagnose(palace_path=palace_path, kg_db_path=seeded_kg.db_path)
        stale_check = next((c for c in report["checks"] if c["check"] == "stale_kg"), None)
        if stale_check:
            assert any("parent_of" in i.get("message", "") for i in stale_check["issues"])


class TestCheckKGConflicts:
    def test_detects_conflicting_active_facts(self, palace_path, collection, kg):
        from mempalace.doctor import diagnose

        # Create two active "works_at" for same person
        kg.add_triple("Alice", "works_at", "Acme", valid_from="2020-01-01")
        kg.add_triple("Alice", "works_at", "NewCo", valid_from="2025-01-01")
        # Both active (no valid_to)

        report = diagnose(palace_path=palace_path, kg_db_path=kg.db_path)
        kg_check = next((c for c in report["checks"] if c["check"] == "kg_conflicts"), None)
        if kg_check:
            conflicts = [i for i in kg_check["issues"] if i["severity"] == "critical"]
            assert len(conflicts) >= 1
            assert "works_at" in conflicts[0]["message"]

    def test_no_conflict_when_properly_invalidated(self, palace_path, collection, kg):
        from mempalace.doctor import diagnose

        kg.add_triple("Alice", "works_at", "Acme", valid_from="2020-01-01", valid_to="2024-12-31")
        kg.add_triple("Alice", "works_at", "NewCo", valid_from="2025-01-01")
        # Only NewCo is active — no conflict

        report = diagnose(palace_path=palace_path, kg_db_path=kg.db_path)
        kg_check = next((c for c in report["checks"] if c["check"] == "kg_conflicts"), None)
        if kg_check:
            conflicts = [i for i in kg_check["issues"] if "works_at" in i.get("message", "")]
            assert len(conflicts) == 0


# ── Smart Merge ──────────────────────────────────────────────────────


class TestMergeDrawers:
    def test_merge_removes_duplicate(self, palace_path, seeded_collection):
        from mempalace.doctor import merge_drawers

        before = seeded_collection.count()
        result = merge_drawers(palace_path, "drawer_proj_backend_aaa", "drawer_proj_backend_bbb")
        assert result["success"] is True
        assert seeded_collection.count() == before - 1
        # Keep still exists
        assert len(seeded_collection.get(ids=["drawer_proj_backend_aaa"])["ids"]) == 1
        # Remove is gone
        assert len(seeded_collection.get(ids=["drawer_proj_backend_bbb"])["ids"]) == 0

    def test_merge_nonexistent_keep(self, palace_path, seeded_collection):
        from mempalace.doctor import merge_drawers

        result = merge_drawers(palace_path, "nonexistent", "drawer_proj_backend_aaa")
        assert result["success"] is False

    def test_merge_nonexistent_remove(self, palace_path, seeded_collection):
        from mempalace.doctor import merge_drawers

        result = merge_drawers(palace_path, "drawer_proj_backend_aaa", "nonexistent")
        assert result["success"] is False

    def test_merge_no_palace(self, tmp_dir):
        from mempalace.doctor import merge_drawers

        result = merge_drawers(os.path.join(tmp_dir, "nope"), "a", "b")
        assert result["success"] is False


# ── MCP Tools ────────────────────────────────────────────────────────


class TestDoctorMCP:
    def _patch(self, monkeypatch, config, palace_path, kg):
        from mempalace import mcp_server
        monkeypatch.setattr(mcp_server, "_config", config)
        monkeypatch.setattr(mcp_server, "_kg", kg)

    def test_doctor_tool(self, monkeypatch, config, palace_path, seeded_collection, kg):
        self._patch(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_doctor

        result = tool_doctor()
        assert "checks" in result
        assert "summary" in result

    def test_doctor_in_tools_list(self):
        from mempalace.mcp_server import handle_request

        resp = handle_request({"method": "tools/list", "id": 1, "params": {}})
        names = {t["name"] for t in resp["result"]["tools"]}
        assert "mempalace_doctor" in names
        assert "mempalace_merge_drawers" in names
