from __future__ import annotations

from pathlib import Path

# Repository root: src/acts/config.py -> parents[2]. Paths do not depend on the working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Downloaded acts: PDFs + metadata manifest written by `acts.fetch`.
DATA_DIR = PROJECT_ROOT / "data" / "raw"
ACTS_MANIFEST = DATA_DIR / "acts.json"
