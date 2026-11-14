"""Generation: retrieved articles → answer with citations.

The model gets numbered fragments [1], [2], … and returns JSON `{"answer", "citations"}`:
the answer text with [n] markers and the numbers of the fragments it used. The citation
itself ("art. 12 ustawy o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003)") is built
in code from the chunk metadata, so the model cannot invent an article number or an act.

Refusal = no cited fragment: the model is told to answer with `REFUSAL` and an empty list
when the fragments do not contain the answer.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

from acts.config import Settings
from acts.llm import chat
from acts.retrieve import retrieve
from acts.store import Hit

REFUSAL = "Wybrane ustawy z 2026 r. nie zawierają odpowiedzi na to pytanie."

SYSTEM_PROMPT = f"""Odpowiadasz na pytania o polskie ustawy WYŁĄCZNIE na podstawie podanych \
fragmentów ustaw.
Zasady:
- Odpowiadaj po polsku, zwięźle i konkretnie; terminy, kwoty i warunki podawaj dokładnie tak, \
jak w przepisach.
- Odpowiadaj tylko na zadane pytanie; pomiń fragmenty, które go nie dotyczą.
- Po każdym zdaniu wstaw numer fragmentu, na którym się opiera, np. „… w ciągu 30 dni [2].”
- W polu citations podaj numery wszystkich fragmentów użytych w odpowiedzi.
- Jeśli fragmenty nie zawierają odpowiedzi na pytanie, napisz dokładnie: „{REFUSAL}” \
i zostaw pustą listę citations. Nie korzystaj z wiedzy spoza fragmentów i nie zgaduj.
"""

# JSON schema of the answer; Ollama constrains decoding to it (`response_format`).
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["answer", "citations"],
}
RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {"name": "Answer", "schema": ANSWER_SCHEMA},
}

_MARKER = re.compile(r"\[(\d+)\]")


class GenerationError(RuntimeError):
    """The model did not return a valid answer, even after a retry."""


@dataclass
class Answer:
    text: str
    citations: list[int]


def cite(metadata: dict) -> str:
    """Citation built from chunk metadata, e.g. 'art. 12 ustawy o … (Dz.U. 2026 poz. 1003)'."""
    act = f"ustawy {metadata['act_title']} ({metadata['address']})"
    art = metadata["art"]

    if art == "preambuła":
        return f"preambuła {act}"

    if art.startswith("załącznik"):
        number = art.removeprefix("załącznik").strip()

        return f"załącznik {'nr ' + number + ' ' if number else ''}do {act}"

    return f"art. {art} {act}"


def format_context(hits: list[Hit]) -> str:
    """Numbered fragments for the model, each with its citation and chapter."""
    fragments = []

    for n, hit in enumerate(hits, start=1):
        header = f"[{n}] {cite(hit.metadata)}"

        if chapter := hit.metadata.get("chapter"):
            header += f", {chapter}"

        fragments.append(f"{header}\n{hit.text}")

    return "\n\n".join(fragments)


def build_messages(question: str, hits: list[Hit]) -> list[dict[str, str]]:
    user = f"Fragmenty ustaw:\n\n{format_context(hits)}\n\nPytanie: {question}"

    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def parse_answer(content: str) -> Answer:
    """Answer from the model's JSON; `ValueError` if it does not match the schema."""
    data = json.loads(content)  # JSONDecodeError is a ValueError

    if not isinstance(data, dict) or not isinstance(data.get("answer"), str):
        raise ValueError('expected an object with a string field "answer"')

    citations = data.get("citations", [])

    if not isinstance(citations, list):
        raise ValueError('"citations" must be a list of fragment numbers')

    # Small models sometimes write "2" or "[2]" instead of 2.
    numbers = [int(n) for n in re.findall(r"\d+", " ".join(map(str, citations)))]

    return Answer(text=data["answer"].strip(), citations=numbers)


def generate(question: str, hits: list[Hit], settings: Settings) -> Answer:
    """Answer the question from the hits; one retry with the error if the JSON is invalid."""
    if not hits:
        return Answer(text=REFUSAL, citations=[])

    messages = build_messages(question, hits)

    for attempt in range(2):
        content = chat(messages, settings, response_format=RESPONSE_FORMAT)

        try:
            return parse_answer(content)
        except ValueError as err:
            if attempt == 1:
                raise GenerationError(f"Invalid answer after a retry: {err}") from err

            messages = [
                *messages,
                {"role": "assistant", "content": content},
                {"role": "user", "content": f"Niepoprawny JSON ({err}). Popraw odpowiedź."},
            ]

    raise AssertionError("unreachable")


@dataclass
class RagResult:
    question: str
    answer: Answer
    hits: list[Hit]
    retrieve_s: float
    generate_s: float

    @property
    def cited(self) -> list[int]:
        """Valid fragment numbers cited by the model: [n] markers in the text ∪ `citations`."""
        numbers = [int(n) for n in _MARKER.findall(self.answer.text)] + self.answer.citations

        return sorted({n for n in numbers if 1 <= n <= len(self.hits)})

    @property
    def refused(self) -> bool:
        return not self.cited

    def cited_hits(self) -> list[tuple[int, Hit]]:
        return [(n, self.hits[n - 1]) for n in self.cited]

    def sources(self) -> list[dict[str, str]]:
        """Cited articles in the test set format: `{"eli", "art"}`, without duplicates."""
        unique = {(hit.eli, hit.art): None for _, hit in self.cited_hits()}

        return [{"eli": eli, "art": art} for eli, art in unique]


def answer(question: str, settings: Settings, k: int | None = None) -> RagResult:
    """Full RAG: retrieve top-k articles, then generate an answer citing them."""
    start = time.perf_counter()
    hits = retrieve(question, settings, k)
    retrieved = time.perf_counter()
    reply = generate(question, hits, settings)

    return RagResult(
        question=question,
        answer=reply,
        hits=hits,
        retrieve_s=round(retrieved - start, 2),
        generate_s=round(time.perf_counter() - retrieved, 2),
    )
