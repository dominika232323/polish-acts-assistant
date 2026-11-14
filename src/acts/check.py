"""Environment smoke test (`make check`).

Checks, step by step, everything the system needs – Ollama and models, the downloaded acts,
the Qdrant index – and finally answers one question end to end. Suggests a fix on failure.
Steps depend on the previous ones, so we stop at the first failure.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable

import httpx

from acts.chunking import load_manifest
from acts.config import ACTS_MANIFEST, DATA_DIR, Settings
from acts.embeddings import embed_documents, embed_query
from acts.generate import answer
from acts.llm import chat
from acts.store import count, get_client, sample_payload

# Below this Ollama silently truncates prompts with a few retrieved articles.
MIN_CONTEXT = 8192

# End-to-end question with a known source: art. 1 of the act on Dzień Inwalidy Wojennego.
SMOKE_QUESTION = "Kiedy obchodzimy Dzień Inwalidy Wojennego?"
SMOKE_SOURCE = {"eli": "DU/2026/179", "art": "1"}


class CheckFailed(Exception):
    """A step failed; `hint` says how to fix it."""

    def __init__(self, message: str, hint: str) -> None:
        super().__init__(message)
        self.hint = hint


def check_ollama(settings: Settings) -> str:
    try:
        response = httpx.get(f"{settings.ollama_url}/api/version", timeout=3)
        version = response.json()["version"]
    except httpx.HTTPError as err:
        raise CheckFailed(
            f"Ollama does not respond at {settings.ollama_url} ({err.__class__.__name__})",
            "Start it: `sudo systemctl start ollama` (or `ollama serve`).",
        ) from err

    return f"Ollama {version}"


def check_models(settings: Settings) -> str:
    tags = httpx.get(f"{settings.ollama_url}/api/tags", timeout=5).json()
    available = {m["name"] for m in tags.get("models", [])}
    available |= {name.removesuffix(":latest") for name in available}
    missing = [m for m in (settings.llm_model, settings.embed_model) if m not in available]

    if missing:
        raise CheckFailed(f"Missing models: {', '.join(missing)}", "Download them: `make pull`.")

    return f"{settings.llm_model}, {settings.embed_model}"


def check_chat(settings: Settings) -> str:
    start = time.perf_counter()

    try:
        answer = chat(
            [{"role": "user", "content": "Odpowiedz jednym słowem: stolica Polski?"}], settings
        )
    except Exception as err:
        raise CheckFailed(
            f"Chat completion failed: {err}",
            f"Check LLM_MODEL={settings.llm_model} and LLM_BASE_URL={settings.llm_base_url}.",
        ) from err

    if not answer.strip():
        raise CheckFailed(
            "The model returned an empty answer",
            "With thinking enabled the answer may be only reasoning – set LLM_REASONING_EFFORT=none.",
        )

    return f"„{answer.strip()[:40]}” ({time.perf_counter() - start:.1f}s)"


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))

    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def check_embedding(settings: Settings) -> str:
    """The query must be closer to the matching passage than to an unrelated one."""
    try:
        passages = embed_documents(
            [
                "Opłata za złożenie wniosku o wydanie opinii indywidualnej wynosi 150 zł.",
                "Związek metropolitalny obejmuje gminy województwa pomorskiego.",
            ],
            settings,
        )
        query = embed_query("Ile kosztuje wniosek o opinię?", settings)
    except Exception as err:
        raise CheckFailed(
            f"Embedding failed: {err}", f"Check EMBED_MODEL={settings.embed_model}."
        ) from err

    related, unrelated = cosine(query, passages[0]), cosine(query, passages[1])

    if related <= unrelated:
        raise CheckFailed(
            f"Query is closer to the unrelated passage ({related:.2f} ≤ {unrelated:.2f})",
            "Check EMBED_MODEL and EMBED_QUERY_INSTRUCTION.",
        )

    return f"dimension {len(query)}, similarity {related:.2f} vs {unrelated:.2f}"


def check_context_window(settings: Settings) -> str:
    """Ollama silently truncates prompts longer than the context window – check its size.

    Runs right after `check_chat`, while the LLM is still loaded and visible in `/api/ps`
    (on a small GPU Ollama unloads it when the embedding model is loaded).
    """
    models = httpx.get(f"{settings.ollama_url}/api/ps", timeout=5).json().get("models", [])
    loaded = next((m for m in models if m["name"].startswith(settings.llm_model)), None)
    ctx = loaded.get("context_length") if loaded else None

    if ctx is None:
        # Another process (e.g. a running eval) may have loaded a different model meanwhile.
        return f"skipped – {settings.llm_model} is not loaded (is another process using Ollama?)"

    if ctx < MIN_CONTEXT:
        raise CheckFailed(
            f"Context window of {settings.llm_model} is {ctx} tokens",
            "Set OLLAMA_CONTEXT_LENGTH=16384 (`sudo systemctl edit ollama`) and restart Ollama.",
        )

    return f"{ctx} tokens"


def check_data() -> str:
    """acts.json and every PDF it lists are downloaded."""
    if not ACTS_MANIFEST.exists():
        raise CheckFailed(f"{ACTS_MANIFEST.name} not found in {DATA_DIR}", "Run `make fetch`.")

    acts = load_manifest(ACTS_MANIFEST)
    missing = [meta["file"] for meta in acts if not (DATA_DIR / meta["file"]).exists()]

    if missing:
        raise CheckFailed(f"Missing PDFs: {', '.join(missing)}", "Run `make fetch`.")

    return f"{len(acts)} acts"


def check_index(settings: Settings) -> str:
    """The collection exists, is not empty and was built with the current embedding model."""
    try:
        client = get_client(settings.qdrant_url)
        points = count(client, settings.collection)
    except RuntimeError as err:  # embedded Qdrant: directory locked by another process
        raise CheckFailed(
            f"Cannot open the index: {err}",
            "Another process (`make ask`, an eval, a notebook) is using it – wait for it to end.",
        ) from err

    if not points:
        raise CheckFailed(
            f"Collection {settings.collection!r} is empty or missing", "Run `make ingest`."
        )

    indexed_with = sample_payload(client, settings.collection).get("embed_model")

    if indexed_with != settings.embed_model:
        raise CheckFailed(
            f"Index built with {indexed_with!r}, but EMBED_MODEL={settings.embed_model!r}",
            "Run `make ingest` again.",
        )

    return f"{points} chunks in {settings.collection!r} ({indexed_with})"


def check_answer(settings: Settings) -> str:
    """One question through the whole pipeline must cite its known source."""
    result = answer(SMOKE_QUESTION, settings)

    if SMOKE_SOURCE not in result.sources():
        found = [h.metadata.get("id") for h in result.hits]
        raise CheckFailed(
            f"The answer does not cite {SMOKE_SOURCE} (retrieved: {found}, "
            f"answer: „{result.answer.text[:80]}”)",
            'Check the index (`make ingest`) and the model (`make ask Q="…" ARGS=--context`).',
        )

    return f"cites art. {SMOKE_SOURCE['art']} ({result.retrieve_s + result.generate_s:.1f}s)"


def steps(settings: Settings) -> list[tuple[str, Callable[[], str]]]:
    """(name, function) pairs; each function returns a short success note or raises CheckFailed."""
    result: list[tuple[str, Callable[[], str]]] = []

    if settings.is_local:
        result += [
            ("Ollama running", lambda: check_ollama(settings)),
            ("Models downloaded", lambda: check_models(settings)),
        ]

    result.append(("Chat", lambda: check_chat(settings)))

    if settings.is_local:
        result.append(("Context window", lambda: check_context_window(settings)))

    result += [
        ("Embedding", lambda: check_embedding(settings)),
        ("Acts downloaded", check_data),
        ("Index", lambda: check_index(settings)),
        ("Answer", lambda: check_answer(settings)),
    ]

    return result


def run_checks(settings: Settings, report: Callable[[str], None] = print) -> bool:
    """Run all steps and report results. Returns True if everything passed."""
    report(f"LLM: {settings.llm_model} @ {settings.llm_base_url}")

    for name, run in steps(settings):
        try:
            detail = run()
        except CheckFailed as err:
            report(f"FAIL {name}: {err}")
            report(f"     → {err.hint}")

            return False
        except Exception as err:
            report(f"FAIL {name}: {err.__class__.__name__}: {err}")

            return False

        report(f"OK   {name}: {detail}")

    report("Everything works.")

    return True
