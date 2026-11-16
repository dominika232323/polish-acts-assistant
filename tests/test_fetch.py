import io
import json
import urllib.error

import pytest

from acts import fetch
from acts.fetch import ACTS, API, fetch_act, fetch_all, get, get_json, is_standalone

PDF = b"%PDF-1.7 fake act"


def act(title: str, type_: str = "Ustawa") -> dict:
    return {"title": title, "type": type_}


def metadata(pos: int, text_pdf: bool = True) -> dict:
    return {
        "ELI": f"DU/2026/{pos}",
        "displayAddress": f"Dz.U. 2026 poz. {pos}",
        "pos": pos,
        "title": f"Ustawa z dnia 1 stycznia 2026 r. nr {pos}",
        "status": "obowiązujący",
        "textPDF": text_pdf,
        "changeDate": "2026-10-26T10:02:14",
    }


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Write downloads into a temporary directory instead of data/raw/."""
    monkeypatch.setattr(fetch, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fetch, "ACTS_MANIFEST", tmp_path / "acts.json")

    return tmp_path


@pytest.fixture
def fake_api(monkeypatch):
    """Replace `get` with a dict lookup {url: bytes}; records requested URLs."""
    responses: dict[str, bytes] = {}
    requested: list[str] = []

    def fake_get(url: str, retries: int = 3) -> bytes:
        requested.append(url)

        if url not in responses:
            raise RuntimeError(f"GET {url} failed: 404")

        return responses[url]

    def add_act(pos: int, pdf: bytes = PDF, text_pdf: bool = True) -> None:
        responses[f"{API}/{pos}"] = json.dumps(metadata(pos, text_pdf)).encode()
        responses[f"{API}/{pos}/text.pdf"] = pdf

    monkeypatch.setattr(fetch, "get", fake_get)
    fake_get.responses = responses
    fake_get.requested = requested
    fake_get.add_act = add_act

    return fake_get


# --------------------------------------------------------------------------- is_standalone


def test_is_standalone_accepts_new_act():
    assert is_standalone(act("Ustawa z dnia 3 lipca 2026 r. o systemach sztucznej inteligencji"))


def test_is_standalone_rejects_amendments_ratifications_and_budget():
    assert not is_standalone(act("Ustawa z dnia 8 października 2026 r. o zmianie ustawy o VAT"))
    assert not is_standalone(act("Ustawa z dnia 18 września 2026 r. o ratyfikacji Traktatu"))
    assert not is_standalone(act("Ustawa budżetowa na rok 2026"))
    assert not is_standalone(act("Rozporządzenie Ministra Zdrowia", type_="Rozporządzenie"))


def test_corpus_has_20_acts():
    assert len(ACTS) == 20


# --------------------------------------------------------------------------- get / get_json


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_get_returns_body_and_sends_user_agent(monkeypatch):
    seen = []

    def fake_urlopen(request, timeout):
        seen.append(request)

        return FakeResponse(b"body")

    monkeypatch.setattr(fetch.urllib.request, "urlopen", fake_urlopen)

    assert get("https://example.org") == b"body"
    assert seen[0].get_header("User-agent") == fetch.USER_AGENT


def test_get_retries_after_timeout(monkeypatch):
    calls = []

    def flaky_urlopen(request, timeout):
        calls.append(request)

        if len(calls) == 1:
            raise TimeoutError("timed out")

        return FakeResponse(b"ok")

    monkeypatch.setattr(fetch.urllib.request, "urlopen", flaky_urlopen)
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)

    assert get("https://example.org") == b"ok"
    assert len(calls) == 2


def test_get_raises_after_last_retry(monkeypatch):
    def failing_urlopen(request, timeout):
        raise urllib.error.URLError("no network")

    sleeps = []
    monkeypatch.setattr(fetch.urllib.request, "urlopen", failing_urlopen)
    monkeypatch.setattr(fetch.time, "sleep", sleeps.append)

    with pytest.raises(RuntimeError, match="no network"):
        get("https://example.org", retries=3)

    assert sleeps == [2, 4]  # no sleep after the last attempt


def test_get_json_parses_response(fake_api):
    fake_api.responses["https://example.org/x"] = b'{"items": [1, 2]}'

    assert get_json("https://example.org/x") == {"items": [1, 2]}


# --------------------------------------------------------------------------- discover


def test_discover_lists_standalone_acts_and_marks_new_ones(fake_api, capsys):
    items = [
        {"pos": 1003, "type": "Ustawa", "title": "Ustawa o systemach sztucznej inteligencji"},
        {"pos": 9999, "type": "Ustawa", "title": "Ustawa o czymś nowym"},
        {"pos": 1446, "type": "Ustawa", "title": "Ustawa o zmianie ustawy o VAT"},
        {"pos": 5, "type": "Rozporządzenie", "title": "Rozporządzenie Ministra"},
    ]
    fake_api.responses[API] = json.dumps({"items": items}).encode()

    fetch.discover()
    lines = capsys.readouterr().out.splitlines()

    assert "   1003  Ustawa o systemach sztucznej inteligencji" in lines
    assert "+  9999  Ustawa o czymś nowym" in lines
    assert not any("1446" in line or "Rozporządzenie" in line for line in lines)


# --------------------------------------------------------------------------- fetch_act


def test_fetch_act_downloads_pdf_and_returns_metadata(fake_api, data_dir):
    fake_api.add_act(1003)

    meta = fetch_act(1003, force=False)

    assert (data_dir / "D20261003.pdf").read_bytes() == PDF
    assert meta["ELI"] == "DU/2026/1003"
    assert meta["displayAddress"] == "Dz.U. 2026 poz. 1003"
    assert meta["file"] == "D20261003.pdf"
    assert meta["source_url"] == f"{API}/1003/text.pdf"
    assert "changeDate" not in meta  # only METADATA_FIELDS are kept
    assert "textPDF" not in meta


def test_fetch_act_pads_position_in_file_name(fake_api, data_dir):
    fake_api.add_act(179)

    assert fetch_act(179, force=False)["file"] == "D20260179.pdf"
    assert (data_dir / "D20260179.pdf").exists()


def test_fetch_act_skips_existing_file(fake_api, data_dir, capsys):
    fake_api.add_act(1003)
    (data_dir / "D20261003.pdf").write_bytes(b"%PDF old")

    fetch_act(1003, force=False)

    assert (data_dir / "D20261003.pdf").read_bytes() == b"%PDF old"
    assert f"{API}/1003/text.pdf" not in fake_api.requested
    assert "already exists" in capsys.readouterr().out


def test_fetch_act_force_redownloads_existing_file(fake_api, data_dir):
    fake_api.add_act(1003)
    (data_dir / "D20261003.pdf").write_bytes(b"%PDF old")

    fetch_act(1003, force=True)

    assert (data_dir / "D20261003.pdf").read_bytes() == PDF


def test_fetch_act_rejects_act_without_pdf(fake_api, data_dir):
    fake_api.add_act(1003, text_pdf=False)

    with pytest.raises(RuntimeError, match="no PDF text"):
        fetch_act(1003, force=False)


def test_fetch_act_rejects_non_pdf_response(fake_api, data_dir):
    fake_api.add_act(1003, pdf=b"<html>error page</html>")

    with pytest.raises(RuntimeError, match="not a PDF"):
        fetch_act(1003, force=False)

    assert not (data_dir / "D20261003.pdf").exists()


# --------------------------------------------------------------------------- fetch_all


def test_fetch_all_writes_manifest_for_all_acts(fake_api, data_dir):
    for pos in ACTS:
        fake_api.add_act(pos)

    assert fetch_all() == []

    manifest = json.loads((data_dir / "acts.json").read_text(encoding="utf-8"))
    assert [m["pos"] for m in manifest] == list(ACTS)
    assert len(list(data_dir.glob("*.pdf"))) == len(ACTS)


def test_fetch_all_reports_failures_and_keeps_the_rest(fake_api, data_dir, capsys):
    missing = list(ACTS)[0]

    for pos in list(ACTS)[1:]:
        fake_api.add_act(pos)

    assert fetch_all() == [missing]

    manifest = json.loads((data_dir / "acts.json").read_text(encoding="utf-8"))
    assert len(manifest) == len(ACTS) - 1
    assert missing not in [m["pos"] for m in manifest]
    assert "ERROR" in capsys.readouterr().out


def test_fetch_all_creates_data_dir(fake_api, tmp_path, monkeypatch):
    target = tmp_path / "nested" / "raw"
    monkeypatch.setattr(fetch, "DATA_DIR", target)
    monkeypatch.setattr(fetch, "ACTS_MANIFEST", target / "acts.json")

    for pos in ACTS:
        fake_api.add_act(pos)

    fetch_all()

    assert (target / "acts.json").exists()
