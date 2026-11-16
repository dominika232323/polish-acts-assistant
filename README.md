# Polish Acts Assistant

A RAG system that answers questions about new Polish acts passed in 2026 and cites the specific
articles it relies on. Questions are asked and answered **in Polish**, like the acts. Data: 20
standalone acts from the 2026 Journal of Laws (Dziennik Ustaw), downloaded from the Sejm API
(`api.sejm.gov.pl/eli`).

```
 ingest (offline)                                          query (online)
 ────────────────                                          ──────────────
 Sejm API → PDF → parse → chunk (1 article) → embed ─┐     question → embed → top-k articles
                                                     ▼                              │
                                        Qdrant (vectors + citation metadata) ◄──────┘
                                                                                    ▼
                    answer + "art. 12 ustawy o … (Dz.U. 2026 poz. 1003)" ◄── LLM (JSON schema)
```

- Everything runs locally: the LLM and the embedding model in [Ollama](https://ollama.com),
  vectors in embedded [Qdrant](https://qdrant.tech) (no server, no Docker).
- Models are called through the `openai` SDK with `base_url` from `.env`, so another
  OpenAI-compatible provider is only a change in `.env`.
- No RAG framework: the whole pipeline is a few short modules in `src/acts/`.

## Contents

1. [Requirements](#requirements)
2. [Usage](#usage)
3. [Data](#data)
4. [System](#system)
5. [Project structure](#project-structure)

## Requirements

### Hardware

- **GPU**: not strictly required – Ollama falls back to CPU, but answers then take much
  longer. 6 GB VRAM is enough for the default 4b model.
- **RAM**: 8 GB minimum, 16 GB recommended.
- **Disk**: ~4 GB for the default models (+6.6 GB for 9b), ~0.4 GB for the Python
  environment, ~20 MB for the acts and the index.

### Software

- [uv](https://docs.astral.sh/uv/) – installs Python ≥ 3.12 and the dependencies into `.venv`
- [Ollama](https://ollama.com) – runs the models locally
- `make` (optional – every target is a one-line wrapper around `uv run python scripts/…`;
  `make help` lists them)

### Ollama context window

Ollama's default context window is too small for several retrieved articles, and longer prompts
are **truncated silently** – the model just does not see part of the context. Set it on the
server (Linux, systemd):

```bash
sudo systemctl edit ollama
#   [Service]
#   Environment="OLLAMA_CONTEXT_LENGTH=16384"
sudo systemctl restart ollama
```

`make check` verifies it (also visible in `ollama ps`, column CONTEXT).

## Usage

### Quick start

```bash
make setup     # install dependencies, create .env from .env.example
make pull      # download the models set in .env (once, ~4 GB)
make fetch     # download the acts into data/raw/
make ingest    # index the acts into Qdrant (~1 minute)
make check     # every step should be OK
make ask Q="Kiedy obchodzimy Dzień Inwalidy Wojennego?"
```

```
Dzień Inwalidy Wojennego obchodzimy 12 kwietnia [1].

Źródła:
  [1] art. 1 ustawy o ustanowieniu Dnia Inwalidy Wojennego (Dz.U. 2026 poz. 179)

(retrieval 0.33s, generation 1.17s)
```

### Commands

| command | |
|---|---|
| `make help` | list all available commands |
| `make setup` | install dependencies (uv), create `.env` |
| `make pull` | download the Ollama models set in `.env` |
| `make check` | smoke test (see [below](#smoke-test)); stops at the first failure and suggests a fix |
| `make fetch` | download the acts (PDF + metadata) into `data/raw/`; `ARGS=--force` re-downloads |
| `make parse` | save the parsed text of the acts into `data/parsed/` (for checking the parser and reading the acts) |
| `make ingest` | parse → chunk → embed → Qdrant; rebuilds the collection |
| `make ask Q="…"` | answer a question with cited articles; `ARGS="-k 8 --context"` = 8 fragments, list all retrieved ones with scores |
| `make test` | unit tests (no network, no models needed) |
| `make coverage` | unit tests with a coverage report (`htmlcov/index.html`) |
| `make lint` | ruff check + format check |

`uv run python scripts/fetch_acts.py --discover` lists all standalone 2026 acts in the API.

### Settings (`.env`)

All settings are in `.env` (created from the commented `.env.example` by `make setup`, never
committed). Variables set in the shell take precedence: `LLM_MODEL=qwen3.5:9b make ask Q="…"`.

| variable | default | |
|---|---|---|
| `LLM_BASE_URL`, `LLM_API_KEY` | `http://localhost:11434/v1`, `ollama` | any OpenAI-compatible server |
| `LLM_MODEL` | `qwen3.5:4b` | `qwen3.5:9b` answers better but is slower |
| `LLM_REASONING_EFFORT` | `none` | disables qwen3.5 thinking (answers in a fraction of the time) |
| `LLM_TEMPERATURE` | `0` | reproducible answers and evaluation |
| `EMBED_MODEL` | `qwen3-embedding:0.6b` | after a change run `make ingest` – vectors of different models are not comparable |
| `EMBED_QUERY_INSTRUCTION` | instruction for qwen3-embedding | prepended to queries only; empty for other models |
| `QDRANT_URL` | `local:.qdrant` | embedded Qdrant in a directory, or `http://localhost:6333` for a server |
| `COLLECTION` | `acts2026` | |
| `TOP_K` | `5` | number of articles passed to the model |

## Data

`make fetch` downloads 20 standalone acts from Dz.U. 2026 – type "Ustawa", without amending
acts ("o zmianie"), ratifications and budget acts. The list is fixed in `src/acts/fetch.py`
(`ACTS`), so the corpus does not change when new acts appear in the API. Topics include AI
systems, space activity, data governance, personal investment accounts, Swiss franc loans,
long-term care for older people and new universities.

| file | | committed |
|---|---|---|
| `data/raw/D2026XXXX.pdf` | texts of the acts (the API serves them only as PDF) | no |
| `data/raw/acts.json` | metadata: ELI (`DU/2026/1003`), address (`Dz.U. 2026 poz. 1003`), title, dates, status, keywords | yes |
| `data/parsed/D2026XXXX.txt` | cleaned text, one paragraph per line (`make parse`) | no |

### Test set

`eval/golden.jsonl` – questions with expected answers and sources, one JSON object per line:

```json
{"id": "ai-001", "question": "Ile Komisja ma czasu na wydanie opinii w sprawie naszego systemu AI?", "expected_answer": "…", "sources": [{"eli": "DU/2026/1003", "art": "12", "ust": "1"}], "type": "easy"}
```

- `sources` – articles that contain the answer: `eli` from `acts.json`, `art` and optional
  `ust` as strings (e.g. `"12a"`, `"479^88a"`, `"preambuła"`)
- `type` – `easy` (one article), `multi` (several sources), `oos` (out of scope: empty
  `sources`, the system should refuse)

`make test` checks the format of the file (`tests/test_golden.py`).

## System

### Parsing

`src/acts/parse.py` turns a PDF into paragraphs of clean text with PyMuPDF. Acts in Dziennik
Ustaw have a regular layout, which the parser relies on:

- every text block is one paragraph – an article (`Art. 12. 1. …`), a paragraph of an article
  (`2. …`), a point (`1) …`) or a heading (`Rozdział 1`); paragraphs split by a page break
  are joined back;
- the act's text is set in 10 pt, so filtering by font size removes footnotes (9 pt) and the
  title header (14 pt); running page headers and the President's signature are removed by text;
- superscript article numbers are kept as `Art. 479^88a`, footnote markers are dropped,
  words hyphenated at line ends are rejoined.

### Chunking

`src/acts/chunking.py` splits every act into **one chunk per article** (1153 chunks from the
20 acts, median ~760 characters). Each chunk keeps everything needed to cite it: `eli`, `art`,
paragraph numbers (`ust`), chapter, page and the act's title and address.

- Articles quoted in provisions amending other acts („Art. 479^88a. …”) stay inside the
  amending article – the chunker tracks „ ” quotes.
- Articles longer than 1500 characters are split at paragraph / point boundaries; later
  parts start with the article's opening paragraph (`Art. 4. Użyte w ustawie określenia
  oznaczają: […]`), so they still say which article they come from.
- The preamble and annexes are separate chunks (`art` = `preambuła`, `załącznik`).
- The text sent to the embedding model starts with the act and chapter name, which gives
  context to short articles.

### Index

`make ingest` embeds the chunks with `EMBED_MODEL` and stores them in Qdrant (cosine distance)
with the chunk text and metadata as payload. Embedded mode keeps the data in `.qdrant/`: no
server is needed, but **only one process can use it at a time** (do not run `make ingest`
while `make ask` or an evaluation is running). The collection is rebuilt from scratch on every
run, so no stale chunks are left after a change in chunking; point ids are derived from chunk
ids (`DU/2026/1003#art12`).

### Retrieval

`src/acts/retrieve.py` embeds the question (with the qwen3-embedding query instruction) and
returns the `TOP_K` closest chunks. It refuses to search an index built with a different
embedding model than `EMBED_MODEL`.

### Answering

`src/acts/generate.py` gives the model numbered fragments, each with its citation and chapter
(`[1] art. 12 ustawy o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003), Rozdział 2 …`),
and asks it to answer only from them, in Polish (the prompt is in Polish too).

- The model returns JSON `{"answer", "citations"}` – the answer with `[n]` markers and the
  numbers of the fragments it used. Ollama constrains decoding to the JSON schema; an invalid
  answer is retried once with the error.
- **Citations are built in code** from the chunk metadata, so the model cannot invent an
  article number or an act.
- When the fragments do not contain the answer, the model replies "Wybrane ustawy z 2026 r.
  nie zawierają odpowiedzi na to pytanie." with no citations – an answer without any valid
  citation counts as a refusal.

For evaluation, `acts.generate.answer(question, settings)` returns a `RagResult`: the answer
text, `sources()` in the test set format (`[{"eli", "art"}]`), `refused`, all retrieved chunks
(`hits`) and timings.

### Smoke test

`make check` checks, in order: Ollama is running, the models are downloaded, chat works, the
context window is large enough, embeddings put a related passage closer than an unrelated one,
the acts are downloaded, the index exists and matches `EMBED_MODEL`, and finally that a known
question ("Kiedy obchodzimy Dzień Inwalidy Wojennego?") is answered citing art. 1 of
Dz.U. 2026 poz. 179.

## Project structure

```
src/acts/
  config.py        shared paths and settings from .env
  llm.py           OpenAI SDK clients, chat completion
  embeddings.py    document and query embeddings
  check.py         environment smoke test
  fetch.py         downloading acts from the Sejm ELI API
  parse.py         PDF of an act → paragraphs of clean text
  chunking.py      paragraphs → chunks: one article per chunk, long ones split
  store.py         Qdrant: collection, upsert, search
  ingest.py        parse → chunk → embed → Qdrant
  retrieve.py      question → top-k chunks
  generate.py      prompt, JSON answer, citations built from metadata
scripts/
  pull_models.py   download Ollama models (make pull)
  check_env.py     smoke test (make check)
  fetch_acts.py    download the acts (make fetch)
  parse_acts.py    save parsed text of the acts (make parse)
  ingest.py        index the acts (make ingest)
  ask.py           answer a question (make ask)
data/raw/          downloaded acts (PDFs not committed) + acts.json
data/parsed/       parsed text of the acts (not committed)
eval/golden.jsonl  test set
tests/             unit tests (no network, no models)
.env.example       settings template (copy to .env)
```
