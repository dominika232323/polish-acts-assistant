"""Format checks for the test set (eval/golden.jsonl).

Each line is one question:
    {"id": "ai-001", "question": "...", "expected_answer": "...",
     "sources": [{"eli": "DU/2026/1003", "art": "12", "ust": "1"}], "type": "easy"}

`sources` point to articles (`ust` is optional); out-of-scope questions ("oos") have no
sources and expect a refusal.
"""

import json
import re

import pytest

from acts.config import ACTS_MANIFEST, GOLDEN_SET

FIELDS = {"id", "question", "expected_answer", "sources", "type"}
TYPES = {"easy", "multi", "oos"}
SOURCE_FIELDS = {"eli", "art", "ust"}
# Article / paragraph numbers are strings: "12", "12a", "479^88a".
NUMBER = re.compile(r"^\d+[a-z]*(\^\w+)?$")
# Parts of an act that are not numbered articles (see acts.chunking).
SPECIAL_ARTICLES = re.compile(r"^(preambuła|załącznik( \d+)?)$")


def load_lines() -> list[tuple[int, str]]:
    lines = GOLDEN_SET.read_text(encoding="utf-8").splitlines()

    return [(n, line) for n, line in enumerate(lines, start=1) if line.strip()]


def load_items() -> list[dict]:
    return [json.loads(line) for _, line in load_lines()]


LINES = load_lines()
LINE_IDS = [f"line{n}" for n, _ in LINES]
KNOWN_ELI = {act["ELI"] for act in json.loads(ACTS_MANIFEST.read_text(encoding="utf-8"))}


def test_golden_set_is_not_empty():
    assert LINES


@pytest.mark.parametrize(("line_no", "line"), LINES, ids=LINE_IDS)
def test_item_format(line_no, line):
    item = json.loads(line)

    assert set(item) == FIELDS, f"line {line_no}: fields {sorted(item)}"
    assert item["type"] in TYPES, f"line {line_no}: type {item['type']!r}"

    for field in ("id", "question", "expected_answer"):
        assert isinstance(item[field], str) and item[field].strip(), (
            f"line {line_no}: empty {field}"
        )

    assert isinstance(item["sources"], list), f"line {line_no}: sources must be a list"

    if item["type"] == "oos":
        assert item["sources"] == [], f"line {line_no}: out-of-scope question has sources"
    else:
        assert item["sources"], f"line {line_no}: no sources"


@pytest.mark.parametrize(("line_no", "line"), LINES, ids=LINE_IDS)
def test_sources_point_to_articles_of_known_acts(line_no, line):
    for source in json.loads(line)["sources"]:
        assert {"eli", "art"} <= set(source) <= SOURCE_FIELDS, f"line {line_no}: {source}"
        assert source["eli"] in KNOWN_ELI, f"line {line_no}: unknown act {source['eli']!r}"
        assert NUMBER.match(source["art"]) or SPECIAL_ARTICLES.match(source["art"]), (
            f"line {line_no}: art {source['art']!r}"
        )

        if "ust" in source:
            assert NUMBER.match(source["ust"]), f"line {line_no}: ust {source['ust']!r}"


def test_ids_are_unique():
    ids = [item["id"] for item in load_items()]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})

    assert not duplicates, f"duplicate ids: {duplicates}"


def test_questions_are_unique():
    questions = [item["question"].strip().lower() for item in load_items()]
    duplicates = sorted({q for q in questions if questions.count(q) > 1})

    assert not duplicates, f"duplicate questions: {duplicates}"


def test_multi_questions_have_several_sources():
    for item in load_items():
        if item["type"] == "multi":
            assert len(item["sources"]) > 1, f"{item['id']}: multi question with one source"
