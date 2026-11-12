.PHONY: help setup fetch test coverage lint

DATA ?=
Q ?=
ARGS ?=

help: ## list commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

setup: ## install dependencies (uv) and create .env
	uv sync
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

fetch: ## download the acts (PDF + metadata) into data/raw/
	uv run python scripts/fetch_acts.py $(ARGS)

test: ## unit tests (no network)
	uv run pytest -q

coverage: ## unit tests with coverage report (HTML: htmlcov/index.html)
	uv run pytest -q --cov=acts --cov-report=term-missing --cov-report=html

lint: ## ruff
	uv run ruff check src tests scripts
	uv run ruff format --check src tests scripts
