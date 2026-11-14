.PHONY: help setup pull check fetch parse ingest ask test coverage lint

Q ?=
ARGS ?=

help: ## list commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

setup: ## install dependencies (uv) and create .env
	uv sync
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

pull: ## download the Ollama models set in .env
	uv run python scripts/pull_models.py

check: ## smoke test: Ollama, models, acts, index and one answer end to end
	uv run python scripts/check_env.py

fetch: ## download the acts (PDF + metadata) into data/raw/
	uv run python scripts/fetch_acts.py $(ARGS)

parse: ## save parsed text of the acts into data/parsed/ (for checking and reading)
	uv run python scripts/parse_acts.py

ingest: ## index the acts into Qdrant: parse → chunk → embed (rebuilds the collection)
	uv run python scripts/ingest.py

ask: ## answer a question with cited articles: make ask Q="…" [ARGS="-k 8 --context"]
	uv run python scripts/ask.py "$(Q)" $(ARGS)

test: ## unit tests (no network)
	uv run pytest -q

coverage: ## unit tests with coverage report (HTML: htmlcov/index.html)
	uv run pytest -q --cov=acts --cov-report=term-missing --cov-report=html

lint: ## ruff
	uv run ruff check src tests scripts
	uv run ruff format --check src tests scripts
