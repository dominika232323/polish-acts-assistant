import os

import pytest

# Settings read from the environment; tests must not depend on the developer's .env or shell.
SETTINGS_VARS = (
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_REASONING_EFFORT",
    "LLM_TEMPERATURE",
    "EMBED_MODEL",
    "EMBED_QUERY_INSTRUCTION",
    "QDRANT_URL",
    "COLLECTION",
    "TOP_K",
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """Start every test without settings variables and restore the environment afterwards.

    `load_dotenv` writes straight into `os.environ`, so a test loading a .env file would
    otherwise leak its values into the following tests.
    """
    saved = dict(os.environ)

    for var in SETTINGS_VARS:
        monkeypatch.delenv(var, raising=False)

    yield

    os.environ.clear()
    os.environ.update(saved)
