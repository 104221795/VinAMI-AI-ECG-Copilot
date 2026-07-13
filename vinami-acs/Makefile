COMPOSE := docker compose

.PHONY: install dev test lint format typecheck migrate seed replay down

install:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"

dev:
	$(COMPOSE) up --build

test:
	$(COMPOSE) run --rm api pytest

lint:
	$(COMPOSE) run --rm api ruff check src apps tests scripts

format:
	$(COMPOSE) run --rm api ruff format src apps tests scripts

typecheck:
	$(COMPOSE) run --rm api mypy src apps scripts

migrate:
	$(COMPOSE) run --rm api alembic upgrade head

seed:
	$(COMPOSE) run --rm api python scripts/seed.py

replay:
	$(COMPOSE) run --rm api python scripts/replay_events.py $(REPLAY_ARGS)

down:
	$(COMPOSE) down --remove-orphans
