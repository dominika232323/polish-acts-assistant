# Polish Acts Assistant

A RAG system that answers questions about new Polish acts passed in 2026 and cites specific
articles as sources. Data: about 20 standalone acts from the 2026 Journal of Laws (Dziennik
Ustaw), downloaded from the Sejm API (`api.sejm.gov.pl/eli`).

## Usage

Requirements: [uv](https://docs.astral.sh/uv/)

```bash
make setup     # dependencies + .env
make fetch     # download the acts into data/raw/
make test      # unit tests
make coverage  # unit tests with coverage report (htmlcov/index.html)
make lint      # ruff
```

`make help` lists all commands.

## Data

`make fetch` downloads 20 standalone acts from Dz.U. 2026 – type "Ustawa", without amending
acts ("o zmianie"), ratifications and budget acts. The list is fixed in `src/acts/fetch.py`
(`ACTS`), so the corpus does not change when new acts appear in the API.

- `data/raw/D2026XXXX.pdf` – act texts (the API serves them only as PDF; not committed)
- `data/raw/acts.json` – metadata: ELI, address (e.g. "Dz.U. 2026 poz. 1003"), title, dates,
  status, keywords (committed)

```bash
make fetch ARGS=--force                         # re-download existing PDFs
uv run python scripts/fetch_acts.py --discover  # list standalone 2026 acts in the API
```

## Test set

`eval/golden.jsonl` – questions with expected answers and sources, one JSON object per line:

```json
{"id": "ai-001", "question": "Ile Komisja ma czasu na wydanie opinii w sprawie naszego systemu AI?", "expected_answer": "…", "sources": [{"eli": "DU/2026/1003", "art": "12", "ust": "1"}], "type": "easy"}
```

- `sources` – articles that contain the answer: `eli` from `acts.json`, `art` and optional
  `ust` as strings (e.g. `"12a"`)
- `type` – `easy` (one article), `multi` (several sources), `oos` (out of scope: empty
  `sources`, the system should refuse)

`make test` checks the format of the file (`tests/test_golden.py`).

## Project structure

```
src/acts/
  config.py       shared paths (data, test set)
  fetch.py        downloading acts from the Sejm ELI API
scripts/
  fetch_acts.py   command line for downloading (make fetch)
data/raw/         downloaded acts + acts.json
eval/golden.jsonl test set
tests/            unit tests (no network)
```
