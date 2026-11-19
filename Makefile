COMPOSE := docker compose -f compose.yaml -f compose.dev.yaml

# local default, the VM sets its own password
export SLURM_LENS_DB_PASSWORD ?= slurm_lens

.PHONY: up down logs db test lint collect status web psql restore

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

db:
	$(COMPOSE) up -d --wait db

test: db
	uv run pytest

lint:
	uv run ruff check && uv run ruff format --check

collect: db
	uv run --env-file .env slurm-lens --config config/local.ini collect --once

status:
	uv run --env-file .env slurm-lens --config config/local.ini status

web:
	cd web && npm run dev

psql:
	$(COMPOSE) exec db psql -U slurm_lens slurm_lens

# replaces the local database with a dump of the VM (pg_dump -Fc), e.g. make restore DUMP=x.dump
restore: db
	$(COMPOSE) exec -T db dropdb -U slurm_lens --force slurm_lens
	$(COMPOSE) exec -T db createdb -U slurm_lens slurm_lens
	$(COMPOSE) exec -T db pg_restore -U slurm_lens -d slurm_lens --no-owner < $(DUMP)
