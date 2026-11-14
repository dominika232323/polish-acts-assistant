"""Ingest: PDFs of acts → chunks → embeddings → Qdrant.

The collection is always rebuilt from scratch: indexing the whole corpus takes a few minutes,
and a fresh collection cannot keep stale chunks after the chunking changes.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from acts.chunking import chunk_all
from acts.config import Settings
from acts.embeddings import embed_documents
from acts.store import count, get_client, recreate_collection, upsert_chunks

# Chunks embedded per progress step (the embedding client batches further internally).
PROGRESS_STEP = 128


@dataclass
class IngestStats:
    acts: int
    chunks: int
    collection: str
    embed_s: float
    total_s: float


def ingest(settings: Settings, report: Callable[[str], None] = print) -> IngestStats:
    """Index all downloaded acts into `settings.collection`."""
    start = time.perf_counter()
    chunks = chunk_all()

    if not chunks:
        raise RuntimeError("No chunks – run `make fetch` first.")

    acts = len({c.eli for c in chunks})
    report(f"{len(chunks)} chunks from {acts} acts, embedding with {settings.embed_model} …")

    embed_start = time.perf_counter()
    vectors: list[list[float]] = []

    for i in range(0, len(chunks), PROGRESS_STEP):
        batch = chunks[i : i + PROGRESS_STEP]
        vectors += embed_documents([c.embedding_text() for c in batch], settings)
        report(f"  {len(vectors)}/{len(chunks)}")

    embed_s = time.perf_counter() - embed_start

    client = get_client(settings.qdrant_url)
    recreate_collection(client, settings.collection, dim=len(vectors[0]))
    upsert_chunks(client, settings.collection, chunks, vectors, settings.embed_model)

    stored = count(client, settings.collection)

    if stored != len(chunks):
        raise RuntimeError(f"Stored {stored} points, expected {len(chunks)} (duplicate chunk ids?)")

    return IngestStats(
        acts=acts,
        chunks=stored,
        collection=settings.collection,
        embed_s=round(embed_s, 1),
        total_s=round(time.perf_counter() - start, 1),
    )
