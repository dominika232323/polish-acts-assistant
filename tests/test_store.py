from dataclasses import replace

import pytest

from acts import ingest as ingest_module
from acts import store
from acts.chunking import Chunk
from acts.config import load_settings
from acts.ingest import ingest
from acts.store import (
    Hit,
    count,
    get_client,
    point_id,
    recreate_collection,
    sample_payload,
    search,
    upsert_chunks,
)


@pytest.fixture(autouse=True)
def fresh_clients(monkeypatch):
    """Every test gets its own in-memory Qdrant (clients are cached per URL)."""
    monkeypatch.setattr(store, "_clients", {})


def chunk(art: str, text: str = "", eli: str = "DU/2026/1003", **kw) -> Chunk:
    return Chunk(
        text=text or f"Art. {art}. Treść.", eli=eli, art=art, address="Dz.U. 2026 poz. 1003", **kw
    )


def settings(**changes):
    return replace(
        load_settings(env_file=None), qdrant_url=":memory:", collection="test", **changes
    )


# --------------------------------------------------------------------------- store


def test_point_id_is_stable_and_unique():
    assert point_id(chunk("12")) == point_id(chunk("12"))
    assert point_id(chunk("12")) != point_id(chunk("13"))
    assert point_id(chunk("4", part=1, parts=2)) != point_id(chunk("4", part=2, parts=2))


def test_upsert_and_search_returns_closest_with_metadata():
    client = get_client(":memory:")
    recreate_collection(client, "test", dim=2)
    upsert_chunks(
        client,
        "test",
        [chunk("12", ust=["1"], chapter="Rozdział 2"), chunk("13")],
        [[1.0, 0.0], [0.0, 1.0]],
        embed_model="fake-embed",
    )

    hits = search(client, "test", [0.9, 0.1], k=2)

    assert [h.art for h in hits] == ["12", "13"]
    assert hits[0].score > hits[1].score
    assert hits[0].text == "Art. 12. Treść."
    assert hits[0].eli == "DU/2026/1003"
    assert hits[0].metadata["ust"] == ["1"]
    assert hits[0].metadata["chapter"] == "Rozdział 2"
    assert hits[0].metadata["id"] == "DU/2026/1003#art12"
    assert hits[0].metadata["embed_model"] == "fake-embed"
    assert "text" not in hits[0].metadata


def test_upserting_same_chunks_twice_does_not_duplicate():
    client = get_client(":memory:")
    recreate_collection(client, "test", dim=2)

    for _ in range(2):
        upsert_chunks(client, "test", [chunk("1"), chunk("2")], [[1.0, 0.0], [0.0, 1.0]], "m")

    assert count(client, "test") == 2


def test_recreate_collection_drops_old_points():
    client = get_client(":memory:")
    recreate_collection(client, "test", dim=2)
    upsert_chunks(client, "test", [chunk("1")], [[1.0, 0.0]], "m")

    recreate_collection(client, "test", dim=3)

    assert count(client, "test") == 0


def test_search_missing_collection_gives_hint():
    with pytest.raises(RuntimeError, match="make ingest"):
        search(get_client(":memory:"), "missing", [1.0, 0.0], k=1)


def test_count_of_missing_collection_is_zero():
    assert count(get_client(":memory:"), "missing") == 0


def test_local_url_points_into_repository(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "PROJECT_ROOT", tmp_path)

    client = get_client("local:qdrant-test")
    recreate_collection(client, "test", dim=2)
    store.close_clients()

    assert (tmp_path / "qdrant-test").is_dir()


def test_sample_payload():
    client = get_client(":memory:")
    assert sample_payload(client, "test") == {}

    recreate_collection(client, "test", dim=2)
    assert sample_payload(client, "test") == {}

    upsert_chunks(client, "test", [chunk("1")], [[1.0, 0.0]], "fake-embed")
    assert sample_payload(client, "test")["embed_model"] == "fake-embed"


def test_get_client_is_cached():
    assert get_client(":memory:") is get_client(":memory:")


def test_hit_accessors():
    hit = Hit(text="t", score=0.5, metadata={"eli": "DU/2026/179", "art": "1"})

    assert (hit.eli, hit.art) == ("DU/2026/179", "1")


# --------------------------------------------------------------------------- ingest


@pytest.fixture
def fake_corpus(monkeypatch):
    chunks = [
        chunk("1", "Art. 1. Ustanawia się Dzień Inwalidy Wojennego.", eli="DU/2026/179"),
        chunk("2", "Art. 2. Dzień jest świętem państwowym.", eli="DU/2026/179"),
        chunk("12", "Art. 12. Komisja wydaje opinię w 30 dni."),
    ]
    embedded: list[str] = []

    def fake_embed(texts, s):
        embedded.extend(texts)

        return [[float(len(t)), 1.0, 0.5] for t in texts]

    monkeypatch.setattr(ingest_module, "chunk_all", lambda: chunks)
    monkeypatch.setattr(ingest_module, "embed_documents", fake_embed)

    return chunks, embedded


def test_ingest_indexes_all_chunks(fake_corpus):
    chunks, embedded = fake_corpus
    lines = []

    stats = ingest(settings(), report=lines.append)

    assert (stats.acts, stats.chunks, stats.collection) == (2, 3, "test")
    assert count(get_client(":memory:"), "test") == 3
    assert embedded == [c.embedding_text() for c in chunks]  # embeddings include the act header
    assert lines[-1] == "  3/3"


def test_ingest_twice_rebuilds_instead_of_duplicating(fake_corpus):
    ingest(settings(), report=lambda line: None)
    ingest(settings(), report=lambda line: None)

    assert count(get_client(":memory:"), "test") == 3


def test_ingest_without_chunks_asks_for_fetch(monkeypatch):
    monkeypatch.setattr(ingest_module, "chunk_all", lambda: [])

    with pytest.raises(RuntimeError, match="make fetch"):
        ingest(settings(), report=lambda line: None)


def test_ingest_detects_duplicate_chunk_ids(monkeypatch):
    monkeypatch.setattr(ingest_module, "chunk_all", lambda: [chunk("1"), chunk("1")])
    monkeypatch.setattr(
        ingest_module, "embed_documents", lambda texts, s: [[1.0, 0.0]] * len(texts)
    )

    with pytest.raises(RuntimeError, match="duplicate"):
        ingest(settings(), report=lambda line: None)
