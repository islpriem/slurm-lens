COMPOSE := docker compose -f compose.yaml -f compose.dev.yaml

# local default, the VM sets its own password
export SLURM_LENS_DB_PASSWORD ?= slurm_lens

.PHONY: up down logs db test lint collect psql

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f collector

db:
	$(COMPOSE) up -d --wait db

test: db
	uv run pytest

lint:
	uv run ruff check && uv run ruff format --check

collect: db
	uv run --env-file .env slurm-lens --config config/local.ini collect --once

psql:
	$(COMPOSE) exec db psql -U slurm_lens slurm_lens
