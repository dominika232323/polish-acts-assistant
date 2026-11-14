"""Vector store: Qdrant (embedded in a directory, a server or in memory).

`QDRANT_URL` can be:
- `local:.qdrant`         – embedded mode: data in a directory relative to the repo root
                            (no server; the directory is locked by one process at a time),
- `http://localhost:6333` – Qdrant server,
- `:memory:`              – in memory (tests).

Each point is one chunk: its vector (cosine distance) and a payload with the chunk text and
metadata (`eli`, `art`, `ust`, `chapter`, …) needed to cite it.
"""

from __future__ import annotations

import atexit
import uuid
from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from acts.chunking import Chunk
from acts.config import PROJECT_ROOT

UPSERT_BATCH = 256

_clients: dict[str, QdrantClient] = {}


def get_client(url: str) -> QdrantClient:
    """Client for `QDRANT_URL` (one per process – embedded mode locks its directory)."""
    if url not in _clients:
        if url == ":memory:":
            _clients[url] = QdrantClient(location=":memory:")
        elif url.startswith("local:"):
            _clients[url] = QdrantClient(path=str(PROJECT_ROOT / url.removeprefix("local:")))
        else:
            _clients[url] = QdrantClient(url=url, timeout=10)

    return _clients[url]


@atexit.register
def close_clients() -> None:
    """Close clients on exit (embedded mode saves data and releases the lock)."""
    for client in _clients.values():
        client.close()

    _clients.clear()


def point_id(chunk: Chunk) -> str:
    """Deterministic point id from the chunk id, so re-indexing overwrites instead of duplicating."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk.id))


def recreate_collection(client: QdrantClient, name: str, dim: int) -> None:
    """Drop the collection (if any) and create an empty one for `dim`-dimensional vectors."""
    if client.collection_exists(name):
        client.delete_collection(name)

    client.create_collection(
        collection_name=name,
        vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
    )


def upsert_chunks(
    client: QdrantClient,
    collection: str,
    chunks: list[Chunk],
    vectors: list[list[float]],
    embed_model: str,
) -> None:
    """Store chunks with their vectors; text and metadata go to the payload."""
    points = [
        models.PointStruct(
            id=point_id(chunk),
            vector=vector,
            payload={"text": chunk.text, "embed_model": embed_model, **chunk.metadata()},
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]

    for i in range(0, len(points), UPSERT_BATCH):
        client.upsert(collection_name=collection, points=points[i : i + UPSERT_BATCH])


@dataclass
class Hit:
    """A search result: chunk text, cosine similarity and the payload metadata."""

    text: str
    score: float
    metadata: dict

    @property
    def eli(self) -> str:
        return self.metadata["eli"]

    @property
    def art(self) -> str:
        return self.metadata["art"]


def search(client: QdrantClient, collection: str, vector: list[float], k: int) -> list[Hit]:
    """Top-k chunks closest to `vector` (dense search)."""
    if not client.collection_exists(collection):
        raise RuntimeError(f"Collection {collection!r} does not exist – run `make ingest` first.")

    response = client.query_points(
        collection_name=collection, query=vector, limit=k, with_payload=True
    )
    hits = []

    for point in response.points:
        payload = dict(point.payload or {})
        hits.append(Hit(text=payload.pop("text", ""), score=point.score, metadata=payload))

    return hits


def count(client: QdrantClient, collection: str) -> int:
    """Number of points in the collection (0 if it does not exist)."""
    if not client.collection_exists(collection):
        return 0

    return client.count(collection_name=collection, exact=True).count
