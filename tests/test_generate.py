import json
from dataclasses import replace

import pytest

from acts import generate as generate_module
from acts import retrieve as retrieve_module
from acts import store
from acts.chunking import Chunk
from acts.config import load_settings
from acts.generate import (
    REFUSAL,
    RESPONSE_FORMAT,
    Answer,
    GenerationError,
    RagResult,
    answer,
    build_messages,
    cite,
    generate,
    parse_answer,
)
from acts.retrieve import check_embed_model, retrieve
from acts.store import Hit, get_client, recreate_collection, upsert_chunks

META = {
    "eli": "DU/2026/1003",
    "act_title": "o systemach sztucznej inteligencji",
    "address": "Dz.U. 2026 poz. 1003",
}


def settings(**changes):
    return replace(
        load_settings(env_file=None), qdrant_url=":memory:", collection="test", **changes
    )


def hit(art: str, eli: str = "DU/2026/1003", **meta) -> Hit:
    return Hit(
        text=f"Art. {art}. Treść.", score=0.7, metadata=META | {"eli": eli, "art": art} | meta
    )


def chunk(art: str, eli: str = "DU/2026/1003") -> Chunk:
    return Chunk(text=f"Art. {art}. Treść.", eli=eli, art=art, address=META["address"])


def reply(text: str = "Opinia w 30 dni [1].", citations=(1,)) -> str:
    return json.dumps({"answer": text, "citations": list(citations)}, ensure_ascii=False)


@pytest.fixture
def fake_chat(monkeypatch):
    """Replace the LLM with canned replies; records the calls."""
    calls = []

    def install(*replies):
        queue = list(replies)

        def chat(messages, s, response_format=None):
            calls.append({"messages": messages, "response_format": response_format})

            return queue.pop(0)

        monkeypatch.setattr(generate_module, "chat", chat)

        return calls

    return install


# --------------------------------------------------------------------------- citations


@pytest.mark.parametrize(
    ("art", "expected"),
    [
        ("12", "art. 12 ustawy o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003)"),
        (
            "479^88a",
            "art. 479^88a ustawy o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003)",
        ),
        ("preambuła", "preambuła ustawy o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003)"),
        (
            "załącznik",
            "załącznik do ustawy o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003)",
        ),
        (
            "załącznik 2",
            "załącznik nr 2 do ustawy o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003)",
        ),
    ],
)
def test_cite(art, expected):
    assert cite(META | {"art": art}) == expected


def test_messages_number_fragments_with_citation_and_chapter():
    messages = build_messages("Pytanie?", [hit("12", chapter="Rozdział 2 Komisja"), hit("13")])
    user = messages[1]["content"]

    assert messages[0]["role"] == "system"
    assert (
        "[1] art. 12 ustawy o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003), Rozdział 2 Komisja\nArt. 12. Treść."
        in user
    )
    assert "[2] art. 13 ustawy" in user
    assert user.endswith("Pytanie: Pytanie?")


# --------------------------------------------------------------------------- parsing


def test_parse_answer():
    assert parse_answer(reply(" Tak [2]. ", [2])) == Answer(text="Tak [2].", citations=[2])


def test_parse_answer_repairs_citation_strings():
    assert parse_answer('{"answer": "x", "citations": ["[2]", "3"]}').citations == [2, 3]


def test_parse_answer_without_citations_is_a_refusal():
    assert parse_answer('{"answer": "x"}').citations == []


@pytest.mark.parametrize(
    "content", ["nie JSON", "[1, 2]", '{"citations": [1]}', '{"answer": "x", "citations": 1}']
)
def test_parse_answer_rejects_invalid(content):
    with pytest.raises(ValueError):
        parse_answer(content)


# --------------------------------------------------------------------------- generation


def test_generate_uses_json_schema(fake_chat):
    calls = fake_chat(reply())

    assert generate("Ile dni?", [hit("12")], settings()) == Answer("Opinia w 30 dni [1].", [1])
    assert calls[0]["response_format"] == RESPONSE_FORMAT


def test_generate_retries_once_with_the_error(fake_chat):
    calls = fake_chat("zepsuty", reply())

    assert generate("Ile dni?", [hit("12")], settings()).citations == [1]
    assert len(calls) == 2
    assert calls[1]["messages"][-2] == {"role": "assistant", "content": "zepsuty"}
    assert "Niepoprawny JSON" in calls[1]["messages"][-1]["content"]


def test_generate_gives_up_after_retry(fake_chat):
    fake_chat("zepsuty", "nadal zepsuty")

    with pytest.raises(GenerationError):
        generate("Ile dni?", [hit("12")], settings())


def test_generate_without_hits_refuses_without_calling_the_model(fake_chat):
    calls = fake_chat()

    assert generate("Ile dni?", [], settings()) == Answer(REFUSAL, [])
    assert calls == []


# --------------------------------------------------------------------------- result


def result(text: str, citations: list[int], hits: list[Hit]) -> RagResult:
    return RagResult("?", Answer(text, citations), hits, retrieve_s=0.1, generate_s=1.0)


def test_cited_joins_markers_and_list_and_drops_invalid_numbers():
    r = result("A [2]. B [7].", [1, 0], [hit("11"), hit("12"), hit("13")])

    assert r.cited == [1, 2]
    assert not r.refused
    assert [n for n, _ in r.cited_hits()] == [1, 2]


def test_no_valid_citation_is_a_refusal():
    assert result(REFUSAL, [], [hit("12")]).refused
    assert result("Coś [9].", [9], [hit("12")]).refused


def test_sources_in_golden_format_without_duplicates():
    hits = [hit("4", part=1), hit("4", part=2), hit("1", eli="DU/2026/179")]
    r = result("A [1][2][3].", [], hits)

    assert r.sources() == [{"eli": "DU/2026/1003", "art": "4"}, {"eli": "DU/2026/179", "art": "1"}]


# --------------------------------------------------------------------------- retrieval + RAG


@pytest.fixture
def index(monkeypatch):
    """In-memory Qdrant with three chunks; the query embedding is chosen per test."""
    monkeypatch.setattr(store, "_clients", {})
    client = get_client(":memory:")
    recreate_collection(client, "test", dim=2)
    chunks = [chunk("11"), chunk("12"), chunk("1", eli="DU/2026/179")]
    vectors = [[1.0, 0.0], [0.8, 0.6], [0.0, 1.0]]
    upsert_chunks(client, "test", chunks, vectors, embed_model="qwen3-embedding:0.6b")

    def set_query(vector):
        monkeypatch.setattr(retrieve_module, "embed_query", lambda q, s: vector)

    return set_query


def test_retrieve_returns_top_k(index):
    index([1.0, 0.1])

    assert [h.art for h in retrieve("?", settings(), k=2)] == ["11", "12"]
    assert len(retrieve("?", settings(top_k=3))) == 3


def test_retrieve_refuses_other_embedding_model(index):
    index([1.0, 0.1])

    with pytest.raises(RuntimeError, match="make ingest"):
        retrieve("?", settings(embed_model="other-model"))


def test_check_embed_model_ignores_empty_results():
    check_embed_model([], settings())


def test_answer_runs_retrieval_and_generation(index, fake_chat):
    index([0.0, 1.0])
    calls = fake_chat(reply("12 kwietnia [1].", [1]))

    r = answer("Kiedy jest Dzień Inwalidy Wojennego?", settings(), k=1)

    assert r.answer.text == "12 kwietnia [1]."
    assert r.sources() == [{"eli": "DU/2026/179", "art": "1"}]
    assert "Art. 1. Treść." in calls[0]["messages"][1]["content"]
    assert r.retrieve_s >= 0 and r.generate_s >= 0
