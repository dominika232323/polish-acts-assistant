"""Save the parsed text of every downloaded act to data/parsed/<file>.txt.

One paragraph per line, without footnotes, page headers and the signature – for checking the
parser and for reading the acts when writing test questions.

Usage:
    uv run python scripts/parse_acts.py   # or: make parse
"""

from __future__ import annotations

import sys

from acts.config import DATA_DIR, PARSED_DIR
from acts.parse import parse_text


def main() -> None:
    pdfs = sorted(DATA_DIR.glob("*.pdf"))

    if not pdfs:
        sys.exit(f"No PDFs in {DATA_DIR} – run `make fetch` first.")

    PARSED_DIR.mkdir(parents=True, exist_ok=True)

    for pdf in pdfs:
        text = parse_text(pdf)
        out = PARSED_DIR / f"{pdf.stem}.txt"
        out.write_text(text + "\n", encoding="utf-8")
        print(f"{pdf.name:<16} {text.count(chr(10)) + 1:>5} paragraphs → {out.name}")


if __name__ == "__main__":
    main()
