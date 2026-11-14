from dataclasses import replace
from types import SimpleNamespace

from acts import embeddings, llm
from acts.config import load_settings
from acts.embeddings import embed_documents, embed_query, format_query
from acts.llm import chat, chat_kwargs


def settings(**changes):
    return replace(load_settings(env_file=None), **changes)


class FakeClient:
    """Stands in for `openai.OpenAI`: records calls, returns canned responses."""

    def __init__(self, answer="Warszawa"):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat))
        self.embeddings = SimpleNamespace(create=self._embed)
        self.answer = answer

    def _chat(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self.answer)

        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    def _embed(self, model, input):
        self.calls.append({"model": model, "input": input})
        data = [SimpleNamespace(embedding=[float(len(text)), 1.0]) for text in input]

        return SimpleNamespace(data=data)


def test_chat_kwargs_disable_thinking_by_default():
    kwargs = chat_kwargs(settings())

    assert kwargs == {"model": "qwen3.5:4b", "temperature": 0.0, "reasoning_effort": "none"}


def test_chat_kwargs_skip_empty_reasoning_effort():
    assert "reasoning_effort" not in chat_kwargs(settings(llm_reasoning_effort=""))


def test_chat_sends_messages_and_returns_text(monkeypatch):
    client = FakeClient(answer="Warszawa")
    monkeypatch.setattr(llm, "llm_client", lambda s: client)
    messages = [{"role": "user", "content": "Stolica Polski?"}]

    assert chat(messages, settings()) == "Warszawa"
    assert client.calls[0]["messages"] == messages
    assert client.calls[0]["model"] == "qwen3.5:4b"


def test_chat_returns_empty_string_for_missing_content(monkeypatch):
    monkeypatch.setattr(llm, "llm_client", lambda s: FakeClient(answer=None))

    assert chat([{"role": "user", "content": "x"}], settings()) == ""


def test_clients_use_base_url_from_settings():
    s = settings(llm_base_url="http://example.org:1234/v1")

    assert str(llm.llm_client(s).base_url).startswith("http://example.org:1234/v1")
    assert str(llm.embed_client(s).base_url).startswith("http://example.org:1234/v1")


def test_format_query_adds_instruction():
    assert (
        format_query("Ile kosztuje?", "Find passages")
        == "Instruct: Find passages\nQuery: Ile kosztuje?"
    )
    assert format_query("Ile kosztuje?", "") == "Ile kosztuje?"


def test_embed_documents_sends_batches_without_instruction(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(embeddings, "embed_client", lambda s: client)
    texts = [f"tekst {i}" for i in range(embeddings.BATCH_SIZE + 5)]

    vectors = embed_documents(texts, settings())

    assert len(vectors) == len(texts)
    assert [len(c["input"]) for c in client.calls] == [embeddings.BATCH_SIZE, 5]
    assert not any("Instruct:" in t for c in client.calls for t in c["input"])


def test_embed_query_adds_instruction(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(embeddings, "embed_client", lambda s: client)

    embed_query("Ile kosztuje wniosek?", settings(embed_query_instruction="Find passages"))

    assert client.calls[0]["input"] == ["Instruct: Find passages\nQuery: Ile kosztuje wniosek?"]
    assert client.calls[0]["model"] == "qwen3-embedding:0.6b"
