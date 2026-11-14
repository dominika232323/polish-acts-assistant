"""Project paths and settings loaded from `.env`.

Paths are shared by all pipeline steps (fetch, ingest, eval). Model settings come from `.env`
(see `.env.example`); variables set in the shell take precedence, e.g.
`LLM_MODEL=qwen3.5:9b make check`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

# Repository root: src/acts/config.py -> parents[2]. Paths do not depend on the working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Downloaded acts: PDFs + metadata manifest written by `acts.fetch`.
DATA_DIR = PROJECT_ROOT / "data" / "raw"
ACTS_MANIFEST = DATA_DIR / "acts.json"

# Test set (golden set): questions with expected answers and sources, one JSON object per line.
GOLDEN_SET = PROJECT_ROOT / "eval" / "golden.jsonl"

ENV_FILE = PROJECT_ROOT / ".env"


def _env(name: str, default: str) -> str:
    """Environment variable or default (an empty string counts as not set)."""
    value = os.getenv(name)

    return value if value not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    """Model settings. Field names match the variables in `.env`."""

    llm_base_url: str
    llm_api_key: str
    llm_model: str
    # "none" disables qwen3.5 thinking; empty string = do not send the parameter.
    llm_reasoning_effort: str
    llm_temperature: float

    embed_model: str
    # Prepended to queries only; empty string = no instruction.
    embed_query_instruction: str

    @property
    def ollama_url(self) -> str:
        """Ollama's own API (`/api/...`) lives next to the OpenAI-compatible `/v1`."""
        return self.llm_base_url.rstrip("/").removesuffix("/v1")

    @property
    def is_local(self) -> bool:
        return urlparse(self.llm_base_url).hostname in ("localhost", "127.0.0.1")


def load_settings(env_file: Path | None = ENV_FILE) -> Settings:
    """Load `.env` (if it exists) and build `Settings`."""
    if env_file:
        load_dotenv(env_file, override=False)

    return Settings(
        llm_base_url=_env("LLM_BASE_URL", "http://localhost:11434/v1"),
        llm_api_key=_env("LLM_API_KEY", "ollama"),
        llm_model=_env("LLM_MODEL", "qwen3.5:4b"),
        llm_reasoning_effort=os.getenv("LLM_REASONING_EFFORT", "none"),
        llm_temperature=float(_env("LLM_TEMPERATURE", "0")),
        embed_model=_env("EMBED_MODEL", "qwen3-embedding:0.6b"),
        embed_query_instruction=os.getenv(
            "EMBED_QUERY_INSTRUCTION",
            "Given a question, retrieve passages from Polish acts that answer it",
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Settings loaded once per process."""
    return load_settings()
