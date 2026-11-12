# polish-acts-assistant

A RAG system that answers questions about new Polish acts passed in 2026 and cites specific
articles as sources. Data: about 20 standalone acts from the 2026 Journal of Laws (Dziennik
Ustaw), downloaded from the Sejm API (`api.sejm.gov.pl/eli`).

## Usage

Requirements: [uv](https://docs.astral.sh/uv/)

```bash
make setup     # dependencies + .env
make test      # unit tests
make lint      # ruff
```

`make help` lists all commands.
