"""Ask a question about the acts: retrieval + answer with cited articles.

Usage:
    uv run python scripts/ask.py "Ile Komisja ma czasu na wydanie opinii?"   # or: make ask Q="…"
    uv run python scripts/ask.py -k 8 --context "…"   # 8 fragments, show all retrieved ones
"""

from __future__ import annotations

import argparse
import sys

from acts.config import get_settings
from acts.generate import answer, cite


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("question")
    parser.add_argument("-k", type=int, help="number of retrieved fragments (default: TOP_K)")
    parser.add_argument("--context", action="store_true", help="list all retrieved fragments")

    args = parser.parse_args()

    if not args.question.strip():
        sys.exit('Error: empty question – make ask Q="…"')

    try:
        result = answer(args.question, get_settings(), k=args.k)
    except RuntimeError as err:
        sys.exit(f"Error: {err}")

    print(result.answer.text)

    if result.cited:
        print("\nŹródła:")

        for n, hit in result.cited_hits():
            print(f"  [{n}] {cite(hit.metadata)}")

    if args.context:
        print("\nRetrieved:")

        for n, hit in enumerate(result.hits, start=1):
            mark = "*" if n in result.cited else " "
            print(f" {mark}[{n}] {hit.score:.3f}  {hit.metadata['id']}")

    print(f"\n(retrieval {result.retrieve_s}s, generation {result.generate_s}s)")


if __name__ == "__main__":
    main()
