"""
test_deep_dive.py — Tests for the topic deep-dive export feature.
"""

import os
import tempfile


class TestDeepDiveCore:
    def test_basic_export(self, palace_path, seeded_collection, kg):
        from mempalace.deep_dive import deep_dive

        result = deep_dive(
            "JWT authentication", palace_path=palace_path, similarity_threshold=0.0
        )
        assert "error" not in result
        assert "markdown" in result
        assert "stats" in result
        assert result["stats"]["total_drawers"] > 0
        assert "# Deep Dive:" in result["markdown"]

    def test_finds_relevant_drawers(self, palace_path, seeded_collection, kg):
        from mempalace.deep_dive import deep_dive

        result = deep_dive("authentication tokens", palace_path=palace_path)
        md = result["markdown"]
        # Should find the auth drawer content
        assert "JWT" in md or "authentication" in md.lower()

    def test_wing_filter(self, palace_path, seeded_collection, kg):
        from mempalace.deep_dive import deep_dive

        result = deep_dive("planning", palace_path=palace_path, wing="notes")
        stats = result["stats"]
        # All results should be from notes wing
        assert all(w == "notes" for w in stats["wings"]) or stats["total_drawers"] == 0
        if stats["total_drawers"] > 0:
            assert "notes" in stats["wings"]

    def test_room_name_matching(self, palace_path, seeded_collection, kg):
        """Rooms whose name matches the topic should be included."""
        from mempalace.deep_dive import deep_dive

        result = deep_dive("backend", palace_path=palace_path)
        stats = result["stats"]
        # "backend" is a room name in seeded data — should find it
        assert stats["room_match_hits"] > 0 or stats["semantic_hits"] > 0
        assert stats["total_drawers"] > 0

    def test_empty_results(self, palace_path, collection, kg):
        """Empty collection should not error."""
        from mempalace.deep_dive import deep_dive

        result = deep_dive("nonexistent topic xyz", palace_path=palace_path)
        assert "error" not in result
        assert result["stats"]["total_drawers"] == 0
        assert "No Results" in result["markdown"] or "No drawers found" in result["markdown"]

    def test_no_palace(self, tmp_dir):
        from mempalace.deep_dive import deep_dive

        result = deep_dive("anything", palace_path=os.path.join(tmp_dir, "nonexistent"))
        assert "error" in result

    def test_deduplication(self, palace_path, seeded_collection, kg):
        """Same drawer found by semantic + room match should appear only once."""
        from mempalace.deep_dive import deep_dive

        result = deep_dive("backend", palace_path=palace_path)
        # The backend drawers should not be duplicated
        md = result["markdown"]
        # Count unique drawer appearances — each drawer's text appears at most once
        assert result["stats"]["total_drawers"] <= seeded_collection.count()

    def test_similarity_threshold(self, palace_path, seeded_collection, kg):
        from mempalace.deep_dive import deep_dive

        # Very high threshold — should find fewer results
        strict = deep_dive(
            "authentication", palace_path=palace_path, similarity_threshold=0.9
        )
        # Normal threshold
        normal = deep_dive(
            "authentication", palace_path=palace_path, similarity_threshold=0.1
        )
        assert strict["stats"]["semantic_hits"] <= normal["stats"]["semantic_hits"]


class TestDeepDiveFileOutput:
    def test_writes_markdown_file(self, palace_path, seeded_collection, kg):
        from mempalace.deep_dive import deep_dive

        tmpdir = tempfile.mkdtemp()
        output = os.path.join(tmpdir, "report.md")
        result = deep_dive("authentication", palace_path=palace_path, output_path=output)

        assert "output_path" in result
        assert os.path.exists(output)
        with open(output, "r", encoding="utf-8") as f:
            content = f.read()
        assert "# Deep Dive:" in content
        assert content == result["markdown"]

    def test_creates_output_directory(self, palace_path, seeded_collection, kg):
        from mempalace.deep_dive import deep_dive

        tmpdir = tempfile.mkdtemp()
        output = os.path.join(tmpdir, "subdir", "report.md")
        result = deep_dive("authentication", palace_path=palace_path, output_path=output)

        assert os.path.exists(output)


class TestDeepDiveMarkdownStructure:
    def test_has_title(self, palace_path, seeded_collection, kg):
        from mempalace.deep_dive import deep_dive

        result = deep_dive("authentication", palace_path=palace_path)
        md = result["markdown"]
        assert md.startswith("# Deep Dive: authentication")

    def test_has_stats_header(self, palace_path, seeded_collection, kg):
        from mempalace.deep_dive import deep_dive

        result = deep_dive("authentication", palace_path=palace_path)
        md = result["markdown"]
        assert "drawers collected" in md
        assert "Generated" in md

    def test_has_wing_room_sections(self, palace_path, seeded_collection, kg):
        from mempalace.deep_dive import deep_dive

        result = deep_dive("database migration", palace_path=palace_path)
        md = result["markdown"]
        if result["stats"]["total_drawers"] > 0:
            assert "### " in md  # wing/room headings
            assert "## Memories" in md

    def test_has_footer(self, palace_path, seeded_collection, kg):
        from mempalace.deep_dive import deep_dive

        result = deep_dive("authentication", palace_path=palace_path)
        md = result["markdown"]
        assert "End of deep dive" in md


class TestDeepDiveWithKG:
    def test_kg_facts_included(self, palace_path, seeded_collection, seeded_kg, tmp_dir):
        from mempalace.deep_dive import deep_dive

        result = deep_dive(
            "Alice", palace_path=palace_path, kg_db_path=seeded_kg.db_path
        )
        md = result["markdown"]
        stats = result["stats"]
        # seeded_kg has facts about Alice
        assert stats["kg_facts"] > 0
        assert "Knowledge Graph" in md

    def test_kg_current_and_historical(self, palace_path, seeded_collection, seeded_kg, tmp_dir):
        from mempalace.deep_dive import deep_dive

        result = deep_dive(
            "Alice", palace_path=palace_path, kg_db_path=seeded_kg.db_path
        )
        md = result["markdown"]
        # Alice works_at has both current (NewCo) and expired (Acme Corp)
        assert "Current Facts" in md or "Historical Facts" in md

    def test_kg_unavailable_no_error(self, palace_path, seeded_collection, tmp_dir):
        """Missing KG should not cause errors — just no KG section."""
        from mempalace.deep_dive import deep_dive

        result = deep_dive(
            "authentication",
            palace_path=palace_path,
            kg_db_path=os.path.join(tmp_dir, "nonexistent.sqlite3"),
        )
        assert "error" not in result
        assert result["stats"]["kg_facts"] == 0


class TestDeepDiveMCPTool:
    def _patch(self, monkeypatch, config, palace_path, kg):
        from mempalace import mcp_server
        assert config.palace_path == palace_path
        monkeypatch.setattr(mcp_server, "_config", config)
        monkeypatch.setattr(mcp_server, "_kg", kg)

    def test_mcp_tool_works(self, monkeypatch, config, palace_path, seeded_collection, kg):
        self._patch(monkeypatch, config, palace_path, kg)
        from mempalace.mcp_server import tool_deep_dive

        result = tool_deep_dive(topic="backend")
        assert "markdown" in result
        # "backend" matches a room name, so room_match should find drawers
        assert result["stats"]["total_drawers"] > 0

    def test_mcp_tool_in_tools_list(self):
        from mempalace.mcp_server import handle_request

        resp = handle_request({"method": "tools/list", "id": 1, "params": {}})
        names = {t["name"] for t in resp["result"]["tools"]}
        assert "mempalace_deep_dive" in names
