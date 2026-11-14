# Polish Acts Assistant

A RAG system that answers questions about new Polish acts passed in 2026 and cites specific
articles as sources. Data: about 20 standalone acts from the 2026 Journal of Laws (Dziennik
Ustaw), downloaded from the Sejm API (`api.sejm.gov.pl/eli`).

## Usage

Requirements: [uv](https://docs.astral.sh/uv/), [Ollama](https://ollama.com) (see below).

```bash
make setup     # dependencies + .env
make pull      # download the Ollama models set in .env
make check     # smoke test: Ollama, models, chat, embedding, context window
make fetch     # download the acts into data/raw/
make parse     # save parsed text of the acts into data/parsed/
make test      # unit tests
make coverage  # unit tests with coverage report (htmlcov/index.html)
make lint      # ruff
```

`make help` lists all commands.

## Models (Ollama)

The LLM and the embedding model run locally in [Ollama](https://ollama.com) and are called
through its OpenAI-compatible API (`openai` SDK with `base_url` from `.env`).

| setting | default | |
|---|---|---|
| `LLM_MODEL` | `qwen3.5:4b` | runs fully on a 6 GB GPU and stays loaded next to the embedding model; `qwen3.5:9b` answers better but is slower |
| `EMBED_MODEL` | `qwen3-embedding:0.6b` | after a change, re-index all documents |
| `LLM_TEMPERATURE` | `0` | reproducible evaluation |
| `LLM_REASONING_EFFORT` | `none` | disables qwen3.5 thinking mode (much faster) |

All settings are in `.env` (created from `.env.example` by `make setup`); variables set in the
shell take precedence, e.g. `LLM_MODEL=qwen3.5:9b make check`.

**Context window** – Ollama's default is too small for several retrieved articles and longer
prompts are truncated silently. Set it on the server (Linux, systemd):

```bash
sudo systemctl edit ollama
#   [Service]
#   Environment="OLLAMA_CONTEXT_LENGTH=16384"
sudo systemctl restart ollama
```

`make check` verifies it (`ollama ps`, column CONTEXT, shows it too).

## Data

`make fetch` downloads 20 standalone acts from Dz.U. 2026 – type "Ustawa", without amending
acts ("o zmianie"), ratifications and budget acts. The list is fixed in `src/acts/fetch.py`
(`ACTS`), so the corpus does not change when new acts appear in the API.

- `data/raw/D2026XXXX.pdf` – act texts (the API serves them only as PDF; not committed)
- `data/raw/acts.json` – metadata: ELI, address (e.g. "Dz.U. 2026 poz. 1003"), title, dates,
  status, keywords (committed)

`make parse` writes the cleaned text of every act to `data/parsed/D2026XXXX.txt` (one
paragraph per line) – for checking the parser and for reading the acts when writing test
questions. The parser (`src/acts/parse.py`) keeps only the act text (10 pt font), so footnotes,
page headers and the President's signature are removed; superscript article numbers are
written as `Art. 479^88a`.

```bash
make fetch ARGS=--force                         # re-download existing PDFs
uv run python scripts/fetch_acts.py --discover  # list standalone 2026 acts in the API
```

## Chunking

`src/acts/chunking.py` splits every act into **one chunk per article** (1153 chunks from the 20
acts). Each chunk keeps what is needed to cite it: `eli`, `art`, paragraph numbers (`ust`),
chapter, page and the act's title and address. Rules:

- articles quoted in provisions amending other acts („Art. 479^88a. …”) stay inside the
  amending article – the chunker tracks „ ” quotes;
- articles longer than 1500 characters are split at paragraph / point boundaries; later
  parts start with the article's opening paragraph (`Art. 4. Użyte w ustawie określenia
  oznaczają: […]`);
- the preamble and annexes are separate chunks (`art` = `preambuła`, `załącznik`);
- the embedding text starts with the act and chapter name, which gives context to short
  articles.

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
  config.py       shared paths and settings from .env
  llm.py          OpenAI SDK clients, chat completion
  embeddings.py   document and query embeddings
  check.py        environment smoke test
  fetch.py        downloading acts from the Sejm ELI API
  parse.py        PDF of an act → paragraphs of clean text
  chunking.py     paragraphs → chunks: one article per chunk, long ones split
scripts/
  pull_models.py  download Ollama models (make pull)
  check_env.py    smoke test (make check)
  fetch_acts.py   command line for downloading (make fetch)
  parse_acts.py   save parsed text of the acts (make parse)
data/raw/         downloaded acts + acts.json
data/parsed/      parsed text of the acts (not committed)
eval/golden.jsonl test set
tests/            unit tests (no network)
```
