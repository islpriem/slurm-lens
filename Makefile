COMPOSE := docker compose

# local default, the VM sets its own password
export SLURM_LENS_DB_PASSWORD ?= slurm_lens

.PHONY: db test lint

db:
	$(COMPOSE) up -d --wait db

test: db
	uv run pytest

lint:
	uv run ruff check && uv run ruff format --check
