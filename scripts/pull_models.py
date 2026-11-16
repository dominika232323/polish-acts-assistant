"""Download the Ollama models set in .env (LLM_MODEL and EMBED_MODEL).

Usage:
    uv run python scripts/pull_models.py   # or: make pull
"""

from __future__ import annotations

import subprocess
import sys

from acts.config import get_settings


def main() -> None:
    settings = get_settings()

    for model in (settings.llm_model, settings.embed_model):
        print(f"==> ollama pull {model}")

        if subprocess.run(["ollama", "pull", model]).returncode != 0:
            sys.exit(f"Failed to pull {model}")


if __name__ == "__main__":
    main()
