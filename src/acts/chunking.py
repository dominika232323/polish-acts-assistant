"""Paragraphs of an act → chunks: one article per chunk, long articles split into parts.

Structure we rely on (see `acts.parse`): every paragraph is one article start ("Art. 12. …"),
paragraph of an article ("2. …"), point ("1) …"), letter point ("a) …") or heading
("Rozdział 1" + its name).

Quoted text: provisions amending other acts quote whole articles of those acts
(„Art. 479^88a. … ”). Such text belongs to the amending article, so we track the depth of
„ ” quotes and only recognise articles, paragraphs and headings outside quotes.

Long articles (over `MAX_CHARS`) are split at paragraph boundaries. Every part after the first
starts with the article's opening paragraph, so it still says which article it comes from.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from acts.config import ACTS_MANIFEST, DATA_DIR
from acts.parse import Paragraph, parse_pdf

# ~400–500 tokens of Polish text; half of all articles are under 650 characters.
MAX_CHARS = 1500
# Opening paragraph repeated in later parts of a split article is cut to this length.
LEAD_CHARS = 300

_ARTICLE = re.compile(r"^Art\. (\d+[a-z]*(?:\^\w+)?)\.(?: |$)")
# Paragraph number: "2. …" or right after the article number: "Art. 12. 1. …".
_PARAGRAPH = re.compile(r"^(?:Art\. \S+ )?(\d+[a-z]*(?:\^\w+)?)\. ")
# Heading alone ("Rozdział 2", its name is the next paragraph) or with the name in the same
# paragraph ("Rozdział 3 Odpowiedzialność cywilna …"). The name starts uppercase, which tells
# it apart from a sentence like "Rozdział 3 stosuje się …".
_CHAPTER = re.compile(r"^((?:Rozdział|Oddział|DZIAŁ|Dział) [\w^]+)(?: ([A-ZĄĆĘŁŃÓŚŹŻ].*))?$")
_ANNEX = re.compile(r"^Załącznik(?: nr (\d+))? do ustawy")
_TITLE = re.compile(r"^Ustawa z dnia .+? r\. ")


@dataclass
class Chunk:
    """A fragment of an act stored in the vector store, with everything needed to cite it."""

    text: str
    eli: str  # "DU/2026/1003"
    art: str  # "12", "479^88a", "preambuła", "załącznik"
    ust: list[str] = field(default_factory=list)  # paragraph numbers present in this chunk
    part: int = 1  # part of a split article (1-based)
    parts: int = 1
    chapter: str = ""  # "Rozdział 2 Komisja Rozwoju i Bezpieczeństwa Sztucznej Inteligencji"
    page: int = 1
    act_title: str = ""  # "o systemach sztucznej inteligencji"
    address: str = ""  # "Dz.U. 2026 poz. 1003"

    @property
    def id(self) -> str:
        """Stable id, e.g. `DU/2026/1003#art12` or `DU/2026/1003#art4/2` (2nd part)."""
        suffix = f"/{self.part}" if self.parts > 1 else ""

        return f"{self.eli}#art{self.art}{suffix}"

    def embedding_text(self) -> str:
        """Text for the embedding model: act and chapter name give context to short articles."""
        header = f"Ustawa {self.act_title} ({self.address})"

        if self.chapter:
            header += f" – {self.chapter}"

        return f"{header}\n{self.text}"

    def metadata(self) -> dict:
        """Payload for the vector store (everything except the text)."""
        meta = asdict(self)
        meta.pop("text")

        return meta | {"id": self.id}


@dataclass
class _Unit:
    """An article (or preamble / annex) before splitting into parts."""

    art: str
    chapter: str
    paragraphs: list[Paragraph] = field(default_factory=list)
    # Paragraph number for each paragraph (None outside numbered paragraphs or inside quotes).
    ust: list[str | None] = field(default_factory=list)


def act_title(title: str) -> str:
    """'Ustawa z dnia 3 lipca 2026 r. o systemach sztucznej inteligencji' → 'o systemach …'."""
    return _TITLE.sub("", title)


def _units(paragraphs: list[Paragraph]) -> list[_Unit]:
    """Group paragraphs into articles; collect chapter headings on the way."""
    units: list[_Unit] = []
    chapter = ""
    pending_heading: str | None = None  # "Rozdział 2" waiting for its name
    depth = 0  # „ ” quote depth at the start of the paragraph
    current_ust: str | None = None

    for index, paragraph in enumerate(paragraphs):
        text = paragraph.text
        quoted = depth > 0 or text.startswith("„")
        depth += text.count("„") - text.count("”")

        if index == 0 and text.startswith("USTAWA"):
            continue  # title – taken from metadata instead

        if not quoted:
            if match := _CHAPTER.match(text):
                if match[2]:
                    chapter = text
                else:
                    pending_heading = text

                continue

            if pending_heading and not _ARTICLE.match(text):
                chapter = f"{pending_heading} {text}"
                pending_heading = None
                continue

            pending_heading = None

            if match := _ARTICLE.match(text):
                units.append(_Unit(art=match[1], chapter=chapter))
                current_ust = None
            elif match := _ANNEX.match(text):
                units.append(
                    _Unit(art=f"załącznik {match[1]}" if match[1] else "załącznik", chapter="")
                )
                current_ust = None
            elif not units:
                units.append(_Unit(art="preambuła", chapter=""))

            if match := _PARAGRAPH.match(text):
                current_ust = match[1]

        units[-1].paragraphs.append(paragraph)
        units[-1].ust.append(current_ust)

    return units


def _lead(unit: _Unit) -> str:
    """Opening paragraph of an article, repeated in its later parts."""
    first = unit.paragraphs[0].text

    return first if len(first) <= LEAD_CHARS else first[:LEAD_CHARS].rsplit(" ", 1)[0] + " …"


def _split(unit: _Unit, max_chars: int) -> list[tuple[list[int], str]]:
    """Pack paragraphs of an article into parts of at most `max_chars` (paragraph indices)."""
    parts: list[list[int]] = [[]]
    size = 0

    for i, paragraph in enumerate(unit.paragraphs):
        if parts[-1] and size + len(paragraph.text) + 1 > max_chars:
            parts.append([])
            size = len(_lead(unit)) + 4

        parts[-1].append(i)
        size += len(paragraph.text) + 1

    result = []

    for n, indices in enumerate(parts):
        body = "\n".join(unit.paragraphs[i].text for i in indices)
        text = body if n == 0 else f"{_lead(unit)}\n[…]\n{body}"
        result.append((indices, text))

    return result


def chunk_act(paragraphs: list[Paragraph], meta: dict, max_chars: int = MAX_CHARS) -> list[Chunk]:
    """Chunks of one act; `meta` is its entry from acts.json."""
    chunks: list[Chunk] = []

    for unit in _units(paragraphs):
        parts = _split(unit, max_chars)

        for n, (indices, text) in enumerate(parts, start=1):
            ust = list(dict.fromkeys(u for i in indices if (u := unit.ust[i]) is not None))
            chunks.append(
                Chunk(
                    text=text,
                    eli=meta["ELI"],
                    art=unit.art,
                    ust=ust,
                    part=n,
                    parts=len(parts),
                    chapter=unit.chapter,
                    page=unit.paragraphs[indices[0]].page,
                    act_title=act_title(meta["title"]),
                    address=meta["displayAddress"],
                )
            )

    return chunks


def load_manifest(path: Path = ACTS_MANIFEST) -> list[dict]:
    """Metadata of the downloaded acts (acts.json)."""
    return json.loads(path.read_text(encoding="utf-8"))


def chunk_all(data_dir: Path = DATA_DIR, max_chars: int = MAX_CHARS) -> list[Chunk]:
    """Parse and chunk every act listed in acts.json."""
    chunks: list[Chunk] = []

    for meta in load_manifest(data_dir / "acts.json"):
        chunks += chunk_act(parse_pdf(data_dir / meta["file"]), meta, max_chars)

    return chunks
