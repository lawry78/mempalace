"""
collection_utils.py — Shared ChromaDB batch iteration helpers.

ChromaDB's col.get() without a limit can exceed SQLite's ~999 variable
limit and cause OOM on large palaces.  These helpers paginate reads in
safe batches.
"""

_DEFAULT_BATCH = 1000


def iter_all_metadata(col, where=None, batch_size=_DEFAULT_BATCH):
    """Yield every metadata dict from *col* in batches.

    Only requests ``["metadatas"]`` — no documents or embeddings —
    keeping memory usage minimal for counting/aggregation tasks.
    """
    offset = 0
    while True:
        kwargs = {"include": ["metadatas"], "limit": batch_size, "offset": offset}
        if where:
            kwargs["where"] = where
        batch = col.get(**kwargs)
        metas = batch.get("metadatas", [])
        if not metas:
            break
        yield from metas
        offset += len(metas)
        if len(metas) < batch_size:
            break


def fetch_all(col, include, where=None, batch_size=_DEFAULT_BATCH):
    """Fetch all matching entries from *col* in batches.

    Returns a dict mirroring ChromaDB's ``.get()`` result shape::

        {"ids": [...], "documents": [...], "metadatas": [...]}

    Only keys listed in *include* (plus ``"ids"`` which is always present)
    are populated; others are omitted.

    Example::

        result = fetch_all(col, include=["documents", "metadatas"], where={"wing": "notes"})
        for doc, meta in zip(result["documents"], result["metadatas"]):
            ...
    """
    collected = {"ids": []}
    for key in include:
        collected[key] = []

    offset = 0
    while True:
        kwargs = {"include": include, "limit": batch_size, "offset": offset}
        if where:
            kwargs["where"] = where
        batch = col.get(**kwargs)
        batch_ids = batch.get("ids", [])
        if not batch_ids:
            break
        collected["ids"].extend(batch_ids)
        for key in include:
            collected[key].extend(batch.get(key, []))
        offset += len(batch_ids)
        if len(batch_ids) < batch_size:
            break

    return collected
