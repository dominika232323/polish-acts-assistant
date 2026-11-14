"""Retrieval: question → query embedding → top-k chunks from Qdrant."""

from __future__ import annotations

from acts.config import Settings
from acts.embeddings import embed_query
from acts.store import Hit, get_client, search


def retrieve(question: str, settings: Settings, k: int | None = None) -> list[Hit]:
    """Top-k chunks most similar to the question (`k` defaults to `TOP_K`)."""
    vector = embed_query(question, settings)
    hits = search(get_client(settings.qdrant_url), settings.collection, vector, k or settings.top_k)
    check_embed_model(hits, settings)

    return hits


def check_embed_model(hits: list[Hit], settings: Settings) -> None:
    """Vectors from different embedding models are not comparable – fail instead of returning
    nonsense when `EMBED_MODEL` changed after indexing."""
    indexed_with = hits[0].metadata.get("embed_model") if hits else None

    if indexed_with and indexed_with != settings.embed_model:
        raise RuntimeError(
            f"Collection indexed with {indexed_with!r}, but EMBED_MODEL={settings.embed_model!r} "
            "– run `make ingest` again."
        )
