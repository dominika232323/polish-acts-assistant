from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest

from acts import check, store
from acts.check import SMOKE_SOURCE, CheckFailed, cosine, run_checks
from acts.chunking import Chunk
from acts.config import load_settings
from acts.generate import Answer, RagResult
from acts.store import Hit, get_client, recreate_collection, upsert_chunks


def settings(**changes):
    return replace(load_settings(env_file=None), **changes)


def fake_get(responses: dict[str, dict]):
    """`httpx.get` replacement: path → JSON body."""

    def get(url, timeout):
        path = url.split("11434")[-1]

        return SimpleNamespace(json=lambda: responses[path])

    return get


def test_cosine():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_check_ollama_reports_version(monkeypatch):
    monkeypatch.setattr(check.httpx, "get", fake_get({"/api/version": {"version": "0.40.16"}}))

    assert check.check_ollama(settings()) == "Ollama 0.40.16"


def test_check_ollama_fails_when_server_is_down(monkeypatch):
    def down(url, timeout):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(check.httpx, "get", down)

    with pytest.raises(CheckFailed, match="does not respond"):
        check.check_ollama(settings())


def test_check_models_accepts_latest_tag(monkeypatch):
    tags = {"models": [{"name": "qwen3.5:4b"}, {"name": "qwen3-embedding:0.6b:latest"}]}
    monkeypatch.setattr(check.httpx, "get", fake_get({"/api/tags": tags}))

    assert "qwen3.5:4b" in check.check_models(settings())


def test_check_models_lists_missing(monkeypatch):
    monkeypatch.setattr(
        check.httpx, "get", fake_get({"/api/tags": {"models": [{"name": "qwen3.5:4b"}]}})
    )

    with pytest.raises(CheckFailed, match="qwen3-embedding:0.6b") as err:
        check.check_models(settings())

    assert "make pull" in err.value.hint


@pytest.mark.parametrize(
    ("loaded", "expected"),
    [
        ([{"name": "qwen3.5:4b", "context_length": 16384}], "16384 tokens"),
        ([{"name": "qwen3-embedding:0.6b", "context_length": 16384}], "skipped"),
        ([], "skipped"),
    ],
)
def test_check_context_window(monkeypatch, loaded, expected):
    monkeypatch.setattr(check.httpx, "get", fake_get({"/api/ps": {"models": loaded}}))

    assert expected in check.check_context_window(settings())


def test_check_context_window_fails_when_too_small(monkeypatch):
    loaded = [{"name": "qwen3.5:4b", "context_length": 4096}]
    monkeypatch.setattr(check.httpx, "get", fake_get({"/api/ps": {"models": loaded}}))

    with pytest.raises(CheckFailed, match="4096") as err:
        check.check_context_window(settings())

    assert "OLLAMA_CONTEXT_LENGTH" in err.value.hint


def test_check_chat_fails_on_empty_answer(monkeypatch):
    monkeypatch.setattr(check, "chat", lambda messages, s: "  ")

    with pytest.raises(CheckFailed, match="empty answer"):
        check.check_chat(settings())


def test_check_chat_fails_when_model_errors(monkeypatch):
    def broken(messages, s):
        raise RuntimeError("model not found")

    monkeypatch.setattr(check, "chat", broken)

    with pytest.raises(CheckFailed, match="model not found"):
        check.check_chat(settings())


def test_check_embedding_needs_related_passage_closer(monkeypatch):
    monkeypatch.setattr(check, "embed_documents", lambda texts, s: [[1.0, 0.0], [0.0, 1.0]])
    monkeypatch.setattr(check, "embed_query", lambda q, s: [0.9, 0.1])
    assert "dimension 2" in check.check_embedding(settings())

    monkeypatch.setattr(check, "embed_query", lambda q, s: [0.1, 0.9])
    with pytest.raises(CheckFailed, match="unrelated"):
        check.check_embedding(settings())


def test_remote_server_skips_ollama_specific_steps():
    names = [name for name, _ in check.steps(settings(llm_base_url="https://api.example.org/v1"))]

    assert names == ["Chat", "Embedding", "Acts downloaded", "Index", "Answer"]


# --------------------------------------------------------------------------- data, index, answer


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(check, "DATA_DIR", tmp_path)
    monkeypatch.setattr(check, "ACTS_MANIFEST", tmp_path / "acts.json")

    return tmp_path


def test_check_data_counts_acts(data_dir):
    (data_dir / "acts.json").write_text('[{"file": "D20260179.pdf"}]')
    (data_dir / "D20260179.pdf").write_bytes(b"%PDF")

    assert check.check_data() == "1 acts"


def test_check_data_lists_missing_pdfs(data_dir):
    (data_dir / "acts.json").write_text('[{"file": "D20260179.pdf"}]')

    with pytest.raises(CheckFailed, match="D20260179.pdf") as err:
        check.check_data()

    assert "make fetch" in err.value.hint


def test_check_data_without_manifest(data_dir):
    with pytest.raises(CheckFailed, match="acts.json"):
        check.check_data()


@pytest.fixture
def index_settings(monkeypatch):
    """Settings pointing at a fresh in-memory Qdrant."""
    monkeypatch.setattr(store, "_clients", {})

    return settings(qdrant_url=":memory:", collection="test")


def fill_index(s, embed_model: str) -> None:
    client = get_client(s.qdrant_url)
    recreate_collection(client, s.collection, dim=2)
    chunks = [Chunk(text="Art. 1.", eli="DU/2026/179", art="1")]
    upsert_chunks(client, s.collection, chunks, [[1.0, 0.0]], embed_model)


def test_check_index_ok(index_settings):
    fill_index(index_settings, index_settings.embed_model)

    assert check.check_index(index_settings).startswith("1 chunks in 'test'")


def test_check_index_missing_collection(index_settings):
    with pytest.raises(CheckFailed, match="empty or missing") as err:
        check.check_index(index_settings)

    assert "make ingest" in err.value.hint


def test_check_index_other_embedding_model(index_settings):
    fill_index(index_settings, "other-model")

    with pytest.raises(CheckFailed, match="other-model"):
        check.check_index(index_settings)


def test_check_index_locked_by_another_process(monkeypatch):
    def locked(url):
        raise RuntimeError("Storage folder .qdrant is already accessed by another instance")

    monkeypatch.setattr(check, "get_client", locked)

    with pytest.raises(CheckFailed, match="already accessed") as err:
        check.check_index(settings())

    assert "Another process" in err.value.hint


def smoke_result(art: str) -> RagResult:
    hit = Hit(text="Art.", score=0.8, metadata={"eli": "DU/2026/179", "art": art, "id": "x"})

    return RagResult("?", Answer("12 kwietnia [1].", [1]), [hit], retrieve_s=0.3, generate_s=1.0)


def test_check_answer_cites_known_source(monkeypatch):
    monkeypatch.setattr(check, "answer", lambda q, s: smoke_result(SMOKE_SOURCE["art"]))

    assert check.check_answer(settings()) == "cites art. 1 (1.3s)"


def test_check_answer_fails_on_wrong_source(monkeypatch):
    monkeypatch.setattr(check, "answer", lambda q, s: smoke_result("2"))

    with pytest.raises(CheckFailed, match="does not cite"):
        check.check_answer(settings())


def test_local_steps_check_context_right_after_chat():
    names = [name for name, _ in check.steps(settings())]

    assert names.index("Context window") == names.index("Chat") + 1


def test_run_checks_stops_at_first_failure(monkeypatch):
    calls = []

    def ok():
        calls.append("ok")
        return "fine"

    def failing():
        raise CheckFailed("broken", "fix it")

    monkeypatch.setattr(check, "steps", lambda s: [("A", ok), ("B", failing), ("C", ok)])
    lines = []

    assert run_checks(settings(), report=lines.append) is False
    assert calls == ["ok"]
    assert any(line.startswith("FAIL B") for line in lines)
    assert any("fix it" in line for line in lines)


def test_run_checks_reports_success(monkeypatch):
    monkeypatch.setattr(check, "steps", lambda s: [("A", lambda: "fine")])
    lines = []

    assert run_checks(settings(), report=lines.append) is True
    assert lines[-1] == "Everything works."
