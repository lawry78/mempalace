"""
test_visualize.py — Tests for the palace visualization feature.
"""

import os
import json
import tempfile


class TestCollectData:
    def test_with_seeded_data(self, palace_path, seeded_collection):
        from mempalace.visualize import collect_data

        data = collect_data(palace_path=palace_path)
        assert "error" not in data
        assert data["total_drawers"] == 4
        assert "project" in data["wings"]
        assert "notes" in data["wings"]
        assert len(data["rooms"]) > 0

    def test_empty_palace(self, palace_path, collection):
        from mempalace.visualize import collect_data

        data = collect_data(palace_path=palace_path)
        assert data["total_drawers"] == 0
        assert data["wings"] == {}

    def test_no_palace(self, tmp_dir):
        from mempalace.visualize import collect_data

        data = collect_data(palace_path=os.path.join(tmp_dir, "nonexistent"))
        assert "error" in data

    def test_graph_nodes_present(self, palace_path, seeded_collection):
        from mempalace.visualize import collect_data

        data = collect_data(palace_path=palace_path)
        # seeded data has backend, frontend, planning rooms
        assert "backend" in data["graph_nodes"] or "frontend" in data["graph_nodes"]

    def test_graph_node_structure(self, palace_path, seeded_collection):
        from mempalace.visualize import collect_data

        data = collect_data(palace_path=palace_path)
        for room, info in data["graph_nodes"].items():
            assert "wings" in info
            assert "count" in info
            assert isinstance(info["wings"], list)
            assert info["count"] > 0

    def test_kg_stats_present(self, palace_path, seeded_collection):
        from mempalace.visualize import collect_data

        data = collect_data(palace_path=palace_path)
        assert "kg_stats" in data
        assert "entities" in data["kg_stats"]

    def test_room_counts_match_total(self, palace_path, seeded_collection):
        from mempalace.visualize import collect_data

        data = collect_data(palace_path=palace_path)
        room_total = sum(data["rooms"].values())
        assert room_total == data["total_drawers"]


class TestGenerateVisualization:
    def test_returns_html(self, palace_path, seeded_collection):
        from mempalace.visualize import generate_visualization

        result = generate_visualization(palace_path=palace_path)
        assert "html" in result
        assert "<!DOCTYPE html>" in result["html"]
        assert "MemPalace" in result["html"]

    def test_writes_file(self, palace_path, seeded_collection):
        from mempalace.visualize import generate_visualization

        tmpdir = tempfile.mkdtemp()
        output = os.path.join(tmpdir, "map.html")
        result = generate_visualization(palace_path=palace_path, output_path=output)

        assert result["output_path"] == output
        assert os.path.exists(output)
        with open(output, "r", encoding="utf-8") as f:
            content = f.read()
        assert content == result["html"]

    def test_creates_output_directory(self, palace_path, seeded_collection):
        from mempalace.visualize import generate_visualization

        tmpdir = tempfile.mkdtemp()
        output = os.path.join(tmpdir, "sub", "dir", "map.html")
        result = generate_visualization(palace_path=palace_path, output_path=output)
        assert os.path.exists(output)

    def test_empty_palace_still_generates(self, palace_path, collection):
        from mempalace.visualize import generate_visualization

        result = generate_visualization(palace_path=palace_path)
        assert "html" in result
        assert "<!DOCTYPE html>" in result["html"]


class TestHTMLContent:
    def test_embeds_data_as_json(self, palace_path, seeded_collection):
        from mempalace.visualize import generate_visualization

        result = generate_visualization(palace_path=palace_path)
        html = result["html"]
        # Data should be embedded as JSON in a script tag
        assert "const DATA = " in html

    def test_contains_canvas(self, palace_path, seeded_collection):
        from mempalace.visualize import generate_visualization

        result = generate_visualization(palace_path=palace_path)
        assert '<canvas id="graph">' in result["html"]

    def test_contains_stats_section(self, palace_path, seeded_collection):
        from mempalace.visualize import generate_visualization

        result = generate_visualization(palace_path=palace_path)
        assert 'id="stats-row"' in result["html"]

    def test_contains_table_section(self, palace_path, seeded_collection):
        from mempalace.visualize import generate_visualization

        result = generate_visualization(palace_path=palace_path)
        assert 'id="table-container"' in result["html"]

    def test_contains_tooltip(self, palace_path, seeded_collection):
        from mempalace.visualize import generate_visualization

        result = generate_visualization(palace_path=palace_path)
        assert 'id="tooltip"' in result["html"]

    def test_self_contained_no_external_urls(self, palace_path, seeded_collection):
        from mempalace.visualize import generate_visualization

        result = generate_visualization(palace_path=palace_path)
        html = result["html"]
        # No external CSS/JS references
        assert "http://" not in html
        assert "https://" not in html
