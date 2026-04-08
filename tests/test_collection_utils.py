"""
test_collection_utils.py — Tests for the shared batch iteration helpers.
"""


class TestIterAllMetadata:
    def test_returns_all_metadata(self, palace_path, seeded_collection):
        from mempalace.collection_utils import iter_all_metadata

        metas = list(iter_all_metadata(seeded_collection))
        assert len(metas) == 4
        wings = {m["wing"] for m in metas}
        assert "project" in wings
        assert "notes" in wings

    def test_with_where_filter(self, palace_path, seeded_collection):
        from mempalace.collection_utils import iter_all_metadata

        metas = list(iter_all_metadata(seeded_collection, where={"wing": "project"}))
        assert len(metas) == 3
        assert all(m["wing"] == "project" for m in metas)

    def test_empty_collection(self, palace_path, collection):
        from mempalace.collection_utils import iter_all_metadata

        metas = list(iter_all_metadata(collection))
        assert metas == []

    def test_respects_batch_size(self, palace_path, seeded_collection):
        """With batch_size=2, should still return all 4 items across batches."""
        from mempalace.collection_utils import iter_all_metadata

        metas = list(iter_all_metadata(seeded_collection, batch_size=2))
        assert len(metas) == 4

    def test_beyond_single_batch(self, palace_path, collection):
        """Insert 150 items, fetch with batch_size=50 — all should arrive."""
        from mempalace.collection_utils import iter_all_metadata

        n = 150
        collection.add(
            ids=[f"d_{i}" for i in range(n)],
            documents=[f"doc {i}" for i in range(n)],
            metadatas=[{"wing": f"w_{i % 3}", "room": "r"} for i in range(n)],
        )
        metas = list(iter_all_metadata(collection, batch_size=50))
        assert len(metas) == n


class TestFetchAll:
    def test_returns_docs_and_metas(self, palace_path, seeded_collection):
        from mempalace.collection_utils import fetch_all

        result = fetch_all(seeded_collection, include=["documents", "metadatas"])
        assert len(result["ids"]) == 4
        assert len(result["documents"]) == 4
        assert len(result["metadatas"]) == 4
        assert "JWT" in result["documents"][0] or "JWT" in result["documents"][1]

    def test_with_where_filter(self, palace_path, seeded_collection):
        from mempalace.collection_utils import fetch_all

        result = fetch_all(
            seeded_collection,
            include=["documents", "metadatas"],
            where={"wing": "notes"},
        )
        assert len(result["ids"]) == 1
        assert result["metadatas"][0]["wing"] == "notes"

    def test_empty_collection(self, palace_path, collection):
        from mempalace.collection_utils import fetch_all

        result = fetch_all(collection, include=["documents", "metadatas"])
        assert result["ids"] == []
        assert result["documents"] == []
        assert result["metadatas"] == []

    def test_metadata_only(self, palace_path, seeded_collection):
        from mempalace.collection_utils import fetch_all

        result = fetch_all(seeded_collection, include=["metadatas"])
        assert len(result["metadatas"]) == 4
        assert "documents" not in result

    def test_beyond_single_batch(self, palace_path, collection):
        from mempalace.collection_utils import fetch_all

        n = 150
        collection.add(
            ids=[f"d_{i}" for i in range(n)],
            documents=[f"doc {i}" for i in range(n)],
            metadatas=[{"wing": "w", "room": "r"} for _ in range(n)],
        )
        result = fetch_all(collection, include=["documents", "metadatas"], batch_size=50)
        assert len(result["ids"]) == n
        assert len(result["documents"]) == n
