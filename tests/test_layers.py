"""
test_layers.py — Tests for the 4-layer memory stack.

Covers Layer0 (identity), Layer1 (essential story), Layer2 (on-demand),
Layer3 (deep search), and the unified MemoryStack interface.
"""

import os


# ── Layer 0 — Identity ────────────────────────────────────────────────


class TestLayer0:
    def test_render_with_file(self, tmp_dir):
        from mempalace.layers import Layer0

        path = os.path.join(tmp_dir, "identity.txt")
        with open(path, "w") as f:
            f.write("I am Atlas, assistant for Alice.")

        l0 = Layer0(identity_path=path)
        text = l0.render()
        assert "Atlas" in text
        assert "Alice" in text

    def test_render_missing_file(self, tmp_dir):
        from mempalace.layers import Layer0

        path = os.path.join(tmp_dir, "nonexistent.txt")
        l0 = Layer0(identity_path=path)
        text = l0.render()
        assert "No identity configured" in text

    def test_render_caches(self, tmp_dir):
        from mempalace.layers import Layer0

        path = os.path.join(tmp_dir, "identity.txt")
        with open(path, "w") as f:
            f.write("Original identity")

        l0 = Layer0(identity_path=path)
        first = l0.render()
        assert "Original identity" in first

        # Overwrite file — cached result should still be returned
        with open(path, "w") as f:
            f.write("Changed identity")

        second = l0.render()
        assert second == first

    def test_token_estimate(self, tmp_dir):
        from mempalace.layers import Layer0

        path = os.path.join(tmp_dir, "identity.txt")
        with open(path, "w") as f:
            f.write("A" * 400)  # 400 chars ≈ 100 tokens

        l0 = Layer0(identity_path=path)
        estimate = l0.token_estimate()
        assert estimate == 100


# ── Layer 1 — Essential Story ─────────────────────────────────────────


class TestLayer1:
    def test_generate_with_data(self, palace_path, seeded_collection):
        from mempalace.layers import Layer1

        l1 = Layer1(palace_path=palace_path)
        text = l1.generate()
        assert "L1" in text
        assert "ESSENTIAL STORY" in text
        # Should contain room names from seeded data
        assert "backend" in text or "frontend" in text or "planning" in text

    def test_generate_empty_collection(self, palace_path, collection):
        from mempalace.layers import Layer1

        l1 = Layer1(palace_path=palace_path)
        text = l1.generate()
        assert "No memories yet" in text

    def test_generate_no_palace(self, tmp_dir):
        from mempalace.layers import Layer1

        l1 = Layer1(palace_path=os.path.join(tmp_dir, "nonexistent"))
        text = l1.generate()
        assert "No palace found" in text

    def test_generate_wing_filter(self, palace_path, seeded_collection):
        from mempalace.layers import Layer1

        l1 = Layer1(palace_path=palace_path, wing="notes")
        text = l1.generate()
        assert "planning" in text
        # Should NOT contain project-only rooms
        assert "backend" not in text
        assert "frontend" not in text

    def test_generate_respects_max_drawers(self, palace_path, collection):
        """Insert more than MAX_DRAWERS and verify truncation."""
        from mempalace.layers import Layer1

        # Insert 20 drawers (MAX_DRAWERS = 15)
        ids = [f"d_{i}" for i in range(20)]
        docs = [f"Memory number {i} about something important." for i in range(20)]
        metas = [
            {
                "wing": "test",
                "room": f"room_{i % 3}",
                "source_file": "gen.py",
                "chunk_index": 0,
                "added_by": "test",
                "filed_at": "2026-01-01T00:00:00",
            }
            for i in range(20)
        ]
        collection.add(ids=ids, documents=docs, metadatas=metas)

        l1 = Layer1(palace_path=palace_path)
        text = l1.generate()
        assert "ESSENTIAL STORY" in text
        # Count "- " entries (each drawer line starts with "  - ")
        entry_count = text.count("  - ")
        assert entry_count <= 15


# ── Layer 2 — On-Demand Retrieval ─────────────────────────────────────


class TestLayer2:
    def test_retrieve_all(self, palace_path, seeded_collection):
        from mempalace.layers import Layer2

        l2 = Layer2(palace_path=palace_path)
        text = l2.retrieve()
        assert "L2" in text
        assert "ON-DEMAND" in text
        assert "4 drawers" in text

    def test_retrieve_wing_filter(self, palace_path, seeded_collection):
        from mempalace.layers import Layer2

        l2 = Layer2(palace_path=palace_path)
        text = l2.retrieve(wing="project")
        assert "3 drawers" in text

    def test_retrieve_room_filter(self, palace_path, seeded_collection):
        from mempalace.layers import Layer2

        l2 = Layer2(palace_path=palace_path)
        text = l2.retrieve(room="backend")
        assert "2 drawers" in text

    def test_retrieve_wing_and_room(self, palace_path, seeded_collection):
        from mempalace.layers import Layer2

        l2 = Layer2(palace_path=palace_path)
        text = l2.retrieve(wing="project", room="frontend")
        assert "1 drawers" in text

    def test_retrieve_no_results(self, palace_path, seeded_collection):
        from mempalace.layers import Layer2

        l2 = Layer2(palace_path=palace_path)
        text = l2.retrieve(wing="nonexistent_wing")
        assert "No drawers found" in text

    def test_retrieve_no_palace(self, tmp_dir):
        from mempalace.layers import Layer2

        l2 = Layer2(palace_path=os.path.join(tmp_dir, "nonexistent"))
        text = l2.retrieve()
        assert "No palace found" in text

    def test_retrieve_n_results(self, palace_path, seeded_collection):
        from mempalace.layers import Layer2

        l2 = Layer2(palace_path=palace_path)
        text = l2.retrieve(n_results=2)
        assert "2 drawers" in text


# ── Layer 3 — Deep Search ────────────────────────────────────────────


class TestLayer3:
    def test_search_basic(self, palace_path, seeded_collection):
        from mempalace.layers import Layer3

        l3 = Layer3(palace_path=palace_path)
        text = l3.search("JWT authentication tokens")
        assert "L3" in text
        assert "SEARCH RESULTS" in text
        # Should find the auth drawer
        assert "backend" in text or "auth" in text.lower()

    def test_search_with_wing_filter(self, palace_path, seeded_collection):
        from mempalace.layers import Layer3

        l3 = Layer3(palace_path=palace_path)
        text = l3.search("planning", wing="notes")
        assert "notes" in text

    def test_search_with_room_filter(self, palace_path, seeded_collection):
        from mempalace.layers import Layer3

        l3 = Layer3(palace_path=palace_path)
        text = l3.search("database", room="backend")
        assert "backend" in text

    def test_search_no_palace(self, tmp_dir):
        from mempalace.layers import Layer3

        l3 = Layer3(palace_path=os.path.join(tmp_dir, "nonexistent"))
        text = l3.search("anything")
        assert "No palace found" in text

    def test_search_raw_returns_list(self, palace_path, seeded_collection):
        from mempalace.layers import Layer3

        l3 = Layer3(palace_path=palace_path)
        hits = l3.search_raw("JWT authentication tokens")
        assert isinstance(hits, list)
        assert len(hits) > 0
        hit = hits[0]
        assert "text" in hit
        assert "wing" in hit
        assert "room" in hit
        assert "similarity" in hit

    def test_search_raw_with_filters(self, palace_path, seeded_collection):
        from mempalace.layers import Layer3

        l3 = Layer3(palace_path=palace_path)
        hits = l3.search_raw("database", wing="project", room="backend")
        assert all(h["wing"] == "project" for h in hits)
        assert all(h["room"] == "backend" for h in hits)

    def test_search_raw_no_palace(self, tmp_dir):
        from mempalace.layers import Layer3

        l3 = Layer3(palace_path=os.path.join(tmp_dir, "nonexistent"))
        hits = l3.search_raw("anything")
        assert hits == []


# ── MemoryStack — unified interface ──────────────────────────────────


class TestMemoryStack:
    def test_wake_up(self, palace_path, seeded_collection, tmp_dir):
        from mempalace.layers import MemoryStack

        identity_path = os.path.join(tmp_dir, "identity.txt")
        with open(identity_path, "w") as f:
            f.write("I am Atlas.")

        stack = MemoryStack(palace_path=palace_path, identity_path=identity_path)
        text = stack.wake_up()
        # Should contain both L0 and L1
        assert "Atlas" in text
        assert "ESSENTIAL STORY" in text

    def test_wake_up_with_wing(self, palace_path, seeded_collection, tmp_dir):
        from mempalace.layers import MemoryStack

        identity_path = os.path.join(tmp_dir, "identity.txt")
        with open(identity_path, "w") as f:
            f.write("I am Atlas.")

        stack = MemoryStack(palace_path=palace_path, identity_path=identity_path)
        text = stack.wake_up(wing="notes")
        assert "Atlas" in text
        assert "planning" in text

    def test_recall(self, palace_path, seeded_collection, tmp_dir):
        from mempalace.layers import MemoryStack

        identity_path = os.path.join(tmp_dir, "identity.txt")
        with open(identity_path, "w") as f:
            f.write("I am Atlas.")

        stack = MemoryStack(palace_path=palace_path, identity_path=identity_path)
        text = stack.recall(wing="project")
        assert "L2" in text
        assert "3 drawers" in text

    def test_search(self, palace_path, seeded_collection, tmp_dir):
        from mempalace.layers import MemoryStack

        identity_path = os.path.join(tmp_dir, "identity.txt")
        with open(identity_path, "w") as f:
            f.write("I am Atlas.")

        stack = MemoryStack(palace_path=palace_path, identity_path=identity_path)
        text = stack.search("JWT tokens")
        assert "L3" in text
        assert "SEARCH RESULTS" in text

    def test_status_with_data(self, palace_path, seeded_collection, tmp_dir):
        from mempalace.layers import MemoryStack

        identity_path = os.path.join(tmp_dir, "identity.txt")
        with open(identity_path, "w") as f:
            f.write("I am Atlas.")

        stack = MemoryStack(palace_path=palace_path, identity_path=identity_path)
        s = stack.status()
        assert s["total_drawers"] == 4
        assert s["L0_identity"]["exists"] is True
        assert s["palace_path"] == palace_path

    def test_status_no_palace(self, tmp_dir):
        from mempalace.layers import MemoryStack

        stack = MemoryStack(
            palace_path=os.path.join(tmp_dir, "nonexistent"),
            identity_path=os.path.join(tmp_dir, "no_identity.txt"),
        )
        s = stack.status()
        assert s["total_drawers"] == 0
        assert s["L0_identity"]["exists"] is False
