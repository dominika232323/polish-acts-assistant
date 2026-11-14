"""Embeddings through the OpenAI-compatible `/v1/embeddings` endpoint.

Queries and documents are embedded differently: qwen3-embedding is trained asymmetrically –
the query gets an instruction describing the task, the document does not.
"""

from __future__ import annotations

from acts.config import Settings
from acts.llm import embed_client

BATCH_SIZE = 32


def embed_documents(texts: list[str], settings: Settings) -> list[list[float]]:
    """Embeddings of documents (chunks), sent in batches of `BATCH_SIZE`."""
    client = embed_client(settings)
    vectors: list[list[float]] = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        response = client.embeddings.create(model=settings.embed_model, input=batch)
        vectors += [item.embedding for item in response.data]

    return vectors


def format_query(query: str, instruction: str) -> str:
    """Query format recommended for qwen3-embedding: `Instruct: ...\\nQuery: ...`."""
    if not instruction:
        return query

    return f"Instruct: {instruction}\nQuery: {query}"


def embed_query(query: str, settings: Settings) -> list[float]:
    """Embedding of a single query (with the instruction, if configured)."""
    text = format_query(query, settings.embed_query_instruction)
    response = embed_client(settings).embeddings.create(model=settings.embed_model, input=[text])

    return response.data[0].embedding
