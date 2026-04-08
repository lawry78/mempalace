"""
test_mcp_server.py — Tests for the MCP server tool handlers and dispatch.

Tests each tool handler directly (unit-level) and the handle_request
dispatch layer (integration-level). Uses isolated palace + KG fixtures
via monkeypatch to avoid touching real data.
"""

import json


def _patch_mcp_server(monkeypatch, config, palace_path, kg):
    """Patch the mcp_server module globals to use test fixtures."""
    from mempalace import mcp_server

    assert getattr(config, "palace_path", None) == palace_path, (
        f"config.palace_path ({getattr(config, 'palace_path', None)!r}) does not match palace_path fixture ({palace_path!r})"
    )
    monkeypatch.setattr(mcp_server, "_config", config)
    monkeypatch.setattr(mcp_server, "_kg", kg)


def _get_collection(palace_path, create=False):
    """Helper to get collection from test palace."""
    import chromadb

    client = chromadb.PersistentClient(path=palace_path)
    if create:
        return client.get_or_create_collection("mempalace_drawers")
    return client.get_collection("mempalace_drawers")


# ── Protocol Layer ──────────────────────────────────────────────────────


class TestHandleRequest:
    def test_initialize(self):
        from mempalace.mcp_server import handle_request

        resp = handle_request({"method": "initialize", "id": 1, "params": {}})
        assert resp["result"]["serverInfo"]["name"] == "mempalace"
        assert resp["id"] == 1

    def test_notifications_initialized_returns_none(self):
        from mempalace.mcp_server import handle_request

        resp = handle_request({"method": "notifications/initialized", "id": None, "params": {}})
        assert resp is None

    def test_tools_list(self):
        from mempalace.mcp_server import handle_request

        resp = handle_request({"method": "tools/list", "id": 2, "params": {}})
        tools = resp["result"]["tools"]
        names = {t["name"] for t in tools}
        assert "mempalace_status" in names
        assert "mempalace_search" in names
        assert "mempalace_add_drawer" in names
        assert "mempalace_kg_add" in names

    def test_unknown_tool(self):
        from mempalace.mcp_server import handle_request

        resp = handle_request(
            {
                "method": "tools/call",
                "id": 3,
                "params": {"name": "nonexistent_tool", "arguments": {}},
            }
        )
        assert resp["error"]["code"] == -32601

    def test_unknown_method(self):
        from mempalace.mcp_server import handle_request

        resp = handle_request({"method": "unknown/method", "id": 4, "params": {}})
        assert resp["error"]["code"] == -32601

    def test_tools_call_dispatches(self, monkeypatch, config, palace_path, seeded_kg):
        _patch_mcp_server(monkeypatch, config, palace_path, seeded_kg)
        from mempalace.mcp_server import handle_request

        # Create a collection so status works
        _get_collection(palace_path, create=True)

        resp = handle_request(
            {
                "method": "tools/call",
                "id": 5,
                "params": {"name": "mempalace_status", "arguments": {}},
            }
        )
        assert "result" in resp
        content = json.loads(resp["result"]["content"][0]["text"])
        assert "total_drawers" in content


# ── Read Tools ──────────────────────────────────────────────────────────


class TestReadTools:
    def test_status_empty_palace(self, monkeypatch, config, palace_path, kg):
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        _get_collection(palace_path, create=True)
        from mempalace.mcp_server import tool_status

        result = tool_status()
        assert result["total_drawers"] == 0
        assert result["wings"] == {}

    def test_status_with_data(self, monkeypatch, config, palace_path, seeded_collection, kg):
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_status

        result = tool_status()
        assert result["total_drawers"] == 4
        assert "project" in result["wings"]
        assert "notes" in result["wings"]

    def test_list_wings(self, monkeypatch, config, palace_path, seeded_collection, kg):
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_list_wings

        result = tool_list_wings()
        assert result["wings"]["project"] == 3
        assert result["wings"]["notes"] == 1

    def test_list_rooms_all(self, monkeypatch, config, palace_path, seeded_collection, kg):
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_list_rooms

        result = tool_list_rooms()
        assert "backend" in result["rooms"]
        assert "frontend" in result["rooms"]
        assert "planning" in result["rooms"]

    def test_list_rooms_filtered(self, monkeypatch, config, palace_path, seeded_collection, kg):
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_list_rooms

        result = tool_list_rooms(wing="project")
        assert "backend" in result["rooms"]
        assert "planning" not in result["rooms"]

    def test_get_taxonomy(self, monkeypatch, config, palace_path, seeded_collection, kg):
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_get_taxonomy

        result = tool_get_taxonomy()
        assert result["taxonomy"]["project"]["backend"] == 2
        assert result["taxonomy"]["project"]["frontend"] == 1
        assert result["taxonomy"]["notes"]["planning"] == 1

    def test_no_palace_returns_error(self, monkeypatch, config, kg):
        config._file_config["palace_path"] = "/nonexistent/path"
        _patch_mcp_server(monkeypatch, config, "/nonexistent/path", kg)
        from mempalace.mcp_server import tool_status

        result = tool_status()
        assert "error" in result

    def test_status_no_aaak_in_response(self, monkeypatch, config, palace_path, seeded_collection, kg):
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_status

        result = tool_status()
        assert "aaak_dialect" not in result

    def test_status_no_recommendations_under_threshold(self, monkeypatch, config, palace_path, seeded_collection, kg):
        """4 drawers is far below the 500 threshold — no recommendations."""
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_status

        result = tool_status()
        assert "recommendations" not in result


# ── Recommendations ────────────────────────────────────────────────────


class TestRecommendations:
    def _seed_large_wing(self, palace_path, wing, n):
        import chromadb

        client = chromadb.PersistentClient(path=palace_path)
        col = client.get_or_create_collection("mempalace_drawers")
        batch_size = 500
        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            ids = [f"rec_{wing}_{i}" for i in range(start, end)]
            docs = [f"content {i}" for i in range(start, end)]
            metas = [
                {"wing": wing, "room": "general", "source_file": "gen.py",
                 "chunk_index": 0, "added_by": "test", "filed_at": "2026-01-01T00:00:00"}
                for _ in range(start, end)
            ]
            col.add(ids=ids, documents=docs, metadatas=metas)
        return col

    def test_recommendation_appears_above_threshold(self, monkeypatch, config, palace_path, kg):
        self._seed_large_wing(palace_path, "big_wing", 600)
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_status

        result = tool_status()
        assert "recommendations" in result
        assert len(result["recommendations"]) == 1
        assert "big_wing" in result["recommendations"][0]
        assert "compress" in result["recommendations"][0]

    def test_no_recommendation_below_threshold(self, monkeypatch, config, palace_path, kg):
        self._seed_large_wing(palace_path, "small_wing", 100)
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_status

        result = tool_status()
        assert "recommendations" not in result

    def test_multiple_recommendations(self, monkeypatch, config, palace_path, kg):
        self._seed_large_wing(palace_path, "wing_a", 600)
        self._seed_large_wing(palace_path, "wing_b", 700)
        self._seed_large_wing(palace_path, "wing_c", 50)  # below threshold
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_status

        result = tool_status()
        assert "recommendations" in result
        assert len(result["recommendations"]) == 2
        rec_text = " ".join(result["recommendations"])
        assert "wing_a" in rec_text
        assert "wing_b" in rec_text
        assert "wing_c" not in rec_text


# ── Search Tool ─────────────────────────────────────────────────────────


class TestSearchTool:
    def test_search_basic(self, monkeypatch, config, palace_path, seeded_collection, kg):
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_search

        result = tool_search(query="JWT authentication tokens")
        assert "results" in result
        assert len(result["results"]) > 0
        # Top result should be the auth drawer
        top = result["results"][0]
        assert "JWT" in top["text"] or "authentication" in top["text"].lower()

    def test_search_with_wing_filter(self, monkeypatch, config, palace_path, seeded_collection, kg):
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_search

        result = tool_search(query="planning", wing="notes")
        assert all(r["wing"] == "notes" for r in result["results"])

    def test_search_with_room_filter(self, monkeypatch, config, palace_path, seeded_collection, kg):
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_search

        result = tool_search(query="database", room="backend")
        assert all(r["room"] == "backend" for r in result["results"])


# ── Write Tools ─────────────────────────────────────────────────────────


class TestWriteTools:
    def test_add_drawer(self, monkeypatch, config, palace_path, kg):
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        _get_collection(palace_path, create=True)
        from mempalace.mcp_server import tool_add_drawer

        result = tool_add_drawer(
            wing="test_wing",
            room="test_room",
            content="This is a test memory about Python decorators and metaclasses.",
        )
        assert result["success"] is True
        assert result["wing"] == "test_wing"
        assert result["room"] == "test_room"
        assert result["drawer_id"].startswith("drawer_test_wing_test_room_")

    def test_add_drawer_duplicate_detection(self, monkeypatch, config, palace_path, kg):
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        _get_collection(palace_path, create=True)
        from mempalace.mcp_server import tool_add_drawer

        content = "This is a unique test memory about Rust ownership and borrowing."
        result1 = tool_add_drawer(wing="w", room="r", content=content)
        assert result1["success"] is True

        result2 = tool_add_drawer(wing="w", room="r", content=content)
        assert result2["success"] is False
        assert result2["reason"] == "duplicate"

    def test_delete_drawer(self, monkeypatch, config, palace_path, seeded_collection, kg):
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_delete_drawer

        result = tool_delete_drawer("drawer_proj_backend_aaa")
        assert result["success"] is True
        assert seeded_collection.count() == 3

    def test_delete_drawer_not_found(self, monkeypatch, config, palace_path, seeded_collection, kg):
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_delete_drawer

        result = tool_delete_drawer("nonexistent_drawer")
        assert result["success"] is False

    def test_check_duplicate(self, monkeypatch, config, palace_path, seeded_collection, kg):
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_check_duplicate

        # Exact match text from seeded_collection should be flagged
        result = tool_check_duplicate(
            "The authentication module uses JWT tokens for session management. "
            "Tokens expire after 24 hours. Refresh tokens are stored in HttpOnly cookies.",
            threshold=0.5,
        )
        assert result["is_duplicate"] is True

        # Unrelated content should not be flagged
        result = tool_check_duplicate(
            "Black holes emit Hawking radiation at the event horizon.",
            threshold=0.99,
        )
        assert result["is_duplicate"] is False


# ── KG Tools ────────────────────────────────────────────────────────────


class TestKGTools:
    def test_kg_add(self, monkeypatch, config, palace_path, kg):
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_kg_add

        result = tool_kg_add(
            subject="Alice",
            predicate="likes",
            object="coffee",
            valid_from="2025-01-01",
        )
        assert result["success"] is True

    def test_kg_query(self, monkeypatch, config, palace_path, seeded_kg):
        _patch_mcp_server(monkeypatch, config, palace_path, seeded_kg)
        from mempalace.mcp_server import tool_kg_query

        result = tool_kg_query(entity="Max")
        assert result["count"] > 0

    def test_kg_invalidate(self, monkeypatch, config, palace_path, seeded_kg):
        _patch_mcp_server(monkeypatch, config, palace_path, seeded_kg)
        from mempalace.mcp_server import tool_kg_invalidate

        result = tool_kg_invalidate(
            subject="Max",
            predicate="does",
            object="chess",
            ended="2026-03-01",
        )
        assert result["success"] is True

    def test_kg_timeline(self, monkeypatch, config, palace_path, seeded_kg):
        _patch_mcp_server(monkeypatch, config, palace_path, seeded_kg)
        from mempalace.mcp_server import tool_kg_timeline

        result = tool_kg_timeline(entity="Alice")
        assert result["count"] > 0

    def test_kg_stats(self, monkeypatch, config, palace_path, seeded_kg):
        _patch_mcp_server(monkeypatch, config, palace_path, seeded_kg)
        from mempalace.mcp_server import tool_kg_stats

        result = tool_kg_stats()
        assert result["entities"] >= 4


# ── Diary Tools ─────────────────────────────────────────────────────────


class TestDiaryTools:
    def test_diary_write_and_read(self, monkeypatch, config, palace_path, kg):
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        _get_collection(palace_path, create=True)
        from mempalace.mcp_server import tool_diary_write, tool_diary_read

        w = tool_diary_write(
            agent_name="TestAgent",
            entry="Today we discussed authentication patterns.",
            topic="architecture",
        )
        assert w["success"] is True
        assert w["agent"] == "TestAgent"

        r = tool_diary_read(agent_name="TestAgent")
        assert r["total"] == 1
        assert r["entries"][0]["topic"] == "architecture"
        assert "authentication" in r["entries"][0]["content"]

    def test_diary_read_empty(self, monkeypatch, config, palace_path, kg):
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        _get_collection(palace_path, create=True)
        from mempalace.mcp_server import tool_diary_read

        r = tool_diary_read(agent_name="Nobody")
        assert r["entries"] == []


# ── Batch Iteration (no 10k cap) ──────────────────────────────────────


class TestBatchIteration:
    """Verify stat tools iterate beyond a single batch (no hardcoded cap)."""

    def _seed_many(self, palace_path, n):
        """Insert *n* drawers spread across multiple wings and rooms."""
        import chromadb

        client = chromadb.PersistentClient(path=palace_path)
        col = client.get_or_create_collection("mempalace_drawers")
        # ChromaDB add supports batches; insert in chunks of 500
        batch_size = 500
        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            ids = [f"d_{i}" for i in range(start, end)]
            docs = [f"content {i}" for i in range(start, end)]
            metas = [
                {
                    "wing": f"wing_{i % 3}",
                    "room": f"room_{i % 5}",
                    "source_file": "gen.py",
                    "chunk_index": 0,
                    "added_by": "test",
                    "filed_at": "2026-01-01T00:00:00",
                }
                for i in range(start, end)
            ]
            col.add(ids=ids, documents=docs, metadatas=metas)
        return col

    def test_status_counts_beyond_batch(self, monkeypatch, config, palace_path, kg):
        """tool_status must report the true count, not a capped value."""
        n = 1500  # exceeds _BATCH (1000)
        self._seed_many(palace_path, n)
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_status

        result = tool_status()
        counted = sum(result["wings"].values())
        assert counted == n, f"Expected {n}, got {counted}"

    def test_list_wings_counts_beyond_batch(self, monkeypatch, config, palace_path, kg):
        n = 1500
        self._seed_many(palace_path, n)
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_list_wings

        result = tool_list_wings()
        counted = sum(result["wings"].values())
        assert counted == n

    def test_list_rooms_counts_beyond_batch(self, monkeypatch, config, palace_path, kg):
        n = 1500
        self._seed_many(palace_path, n)
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_list_rooms

        result = tool_list_rooms()
        counted = sum(result["rooms"].values())
        assert counted == n

    def test_list_rooms_filtered_beyond_batch(self, monkeypatch, config, palace_path, kg):
        n = 1500
        self._seed_many(palace_path, n)
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_list_rooms

        result = tool_list_rooms(wing="wing_0")
        counted = sum(result["rooms"].values())
        assert counted == 500  # n=1500, i%3==0 → 500

    def test_taxonomy_counts_beyond_batch(self, monkeypatch, config, palace_path, kg):
        n = 1500
        self._seed_many(palace_path, n)
        _patch_mcp_server(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_get_taxonomy

        result = tool_get_taxonomy()
        total = sum(
            count for wing in result["taxonomy"].values() for count in wing.values()
        )
        assert total == n
