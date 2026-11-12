.PHONY: help setup test lint

DATA ?=
Q ?=
ARGS ?=

help: ## list commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

setup: ## install dependencies (uv) and create .env
	uv sync
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

test: ## unit tests (no network)
	uv run pytest -q

lint: ## ruff
	uv run ruff check src tests
	uv run ruff format --check src tests
