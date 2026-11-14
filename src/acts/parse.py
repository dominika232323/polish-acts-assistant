"""PDF of an act → list of paragraphs of clean text.

Acts in Dziennik Ustaw have a regular layout, which PyMuPDF exposes well:
- every text block is one paragraph: an article ("Art. 12. 1. …"), a paragraph of an article
  ("2. …"), a point ("1) …"), a heading ("Rozdział 1");
- the act's text is set in 10 pt; footnotes in 9 pt, footnote markers in 6–6.5 pt, the title
  header on page 1 in 14 pt and more – so filtering by font size removes them;
- each page from the 2nd one starts with a running header "Dziennik Ustaw / – 5 – / Poz. 1003"
  (in 10 pt), which we remove by its text.

Small spans inside a line of act text are superscripts: article numbers written as "[88a]"
("Art. 479[88a]" = art. 479 with superscript 88a – we write it as "Art. 479^88a"), footnote
markers "1)" (dropped) or units ("m" + "2" = m²; kept as digits).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

# Act text is 10 pt; footnotes (9 pt) and the page 1 title header (14 pt+) fall outside.
BODY_MIN_SIZE = 9.5
BODY_MAX_SIZE = 11.0

_RUNNING_HEADER = re.compile(r"^(Dziennik Ustaw|– \d+ –|Poz\. \d+)$")
_SIGNATURE = re.compile(r"^(Prezydent Rzeczypospolitej Polskiej|Marszałek Sejmu):")
# Lowercase start that is NOT a letter point ("a) …", "ab) …") – the rest of the previous
# paragraph (continued on the next page, or split into two blocks by the PDF).
_CONTINUATION = re.compile(r"^(?![a-z]{1,2}\) )[a-ząćęłńóśźż]")
_SUPERSCRIPT_NUMBER = re.compile(r"^\[(\w+)\]$")
_FOOTNOTE_MARKER = re.compile(r"^\d+\)(, ?\d+\))*$")
# Words glued in the PDF itself: "niepóźniej niż" → "nie później niż". "niemniej" is also
# a real word ("niemniej jednak"), so it is split only before "niż".
_GLUED = re.compile(r"\bnie(później|wcześniej|więcej|dłużej|krócej)\b|\bnie(mniej)(?= niż)")
# Word split at the end of a line: "inteli-" + "gencji" (the next part starts lowercase).
_HYPHENATED = re.compile(r"(\w)-$")


@dataclass
class Paragraph:
    """One paragraph of the act with the page it starts on (counted from 1)."""

    text: str
    page: int


def _join_lines(lines: list[str]) -> str:
    """Join the lines of one paragraph, rejoining words split with a hyphen."""
    text = ""

    for line in lines:
        if not text:
            text = line
        elif _HYPHENATED.search(text) and line[:1].islower():
            text = text[:-1] + line
        else:
            text = f"{text} {line}"

    return text


def _span_text(span: dict) -> str:
    """Text of a span in a body line: body font as is, superscripts converted or dropped."""
    if BODY_MIN_SIZE <= span["size"] <= BODY_MAX_SIZE:
        return span["text"]

    if span["size"] > BODY_MAX_SIZE:
        return ""

    small = span["text"].strip()

    if match := _SUPERSCRIPT_NUMBER.match(small):
        return f"^{match[1]}"

    if _FOOTNOTE_MARKER.match(small):
        return ""

    return small


def _body_lines(block: dict) -> list[str]:
    """Lines of a block written in the body font, without running headers.

    Lines without any body-font span (footnotes, the title header) are skipped entirely.
    """
    lines = []

    for line in block.get("lines", []):
        spans = line["spans"]

        if not any(BODY_MIN_SIZE <= s["size"] <= BODY_MAX_SIZE for s in spans):
            continue

        text = "".join(_span_text(span) for span in spans)
        text = re.sub(r"\s+", " ", text).strip()

        if text and not _RUNNING_HEADER.match(text):
            lines.append(text)

    return lines


def parse_pdf(path: Path) -> list[Paragraph]:
    """Paragraphs of the act in reading order, without footnotes, headers and signature."""
    paragraphs: list[Paragraph] = []

    with pymupdf.open(path) as doc:
        for page_no, page in enumerate(doc, start=1):
            for block in page.get_text("dict")["blocks"]:
                lines = _body_lines(block)

                if not lines:
                    continue

                text = _GLUED.sub(lambda m: f"nie {m[1] or m[2]}", _join_lines(lines))

                if _SIGNATURE.match(text):
                    continue

                if paragraphs and _CONTINUATION.match(text):
                    paragraphs[-1].text = _join_lines([paragraphs[-1].text, text])
                else:
                    paragraphs.append(Paragraph(text, page_no))

    return paragraphs


def parse_text(path: Path) -> str:
    """Whole act as text, one paragraph per line (handy for reading and debugging)."""
    return "\n".join(p.text for p in parse_pdf(path))
