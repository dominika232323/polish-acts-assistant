"""Smoke test: Ollama, models, chat, embedding, context window, acts, index, one answer.

Usage:
    uv run python scripts/check_env.py   # or: make check
"""

from __future__ import annotations

import sys

from acts.check import run_checks
from acts.config import get_settings


def main() -> None:
    if not run_checks(get_settings()):
        sys.exit(1)


if __name__ == "__main__":
    main()
