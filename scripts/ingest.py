"""Index the downloaded acts: parse → chunk → embed → Qdrant (collection rebuilt from scratch).

Usage:
    uv run python scripts/ingest.py   # or: make ingest
"""

from __future__ import annotations

import sys

from acts.config import get_settings
from acts.ingest import ingest


def main() -> None:
    try:
        stats = ingest(get_settings())
    except RuntimeError as err:
        sys.exit(f"Error: {err}")

    print(
        f"Indexed {stats.chunks} chunks from {stats.acts} acts into {stats.collection!r} "
        f"in {stats.total_s}s (embedding: {stats.embed_s}s)"
    )


if __name__ == "__main__":
    main()
