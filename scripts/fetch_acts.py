"""Download the selected 2026 acts (PDF + metadata) into data/raw/.

Usage:
    uv run python scripts/fetch_acts.py             # download (or: make fetch)
    uv run python scripts/fetch_acts.py --force     # re-download existing files
    uv run python scripts/fetch_acts.py --discover  # list standalone 2026 acts in the API
"""

from __future__ import annotations

import argparse
import sys

from acts.fetch import discover, fetch_all


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-download existing PDFs")
    parser.add_argument("--discover", action="store_true", help="list standalone acts in the API")

    args = parser.parse_args()

    if args.discover:
        discover()
        return

    if failed := fetch_all(force=args.force):
        sys.exit(f"Failed: {failed}")


if __name__ == "__main__":
    main()
