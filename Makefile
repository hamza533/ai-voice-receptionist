# Same commands for every human and AI tool. On machines without uv/Node (e.g. Windows),
# run any target inside the toolbox container:  docker compose run --rm dev make <target>

SHELL := /bin/bash
UV ?= uv
COMPOSE ?= docker compose
TEST_DATABASE_URL ?= postgresql+psycopg://receptionist:receptionist@localhost:55432/receptionist_test
EVAL_DATABASE_URL ?= postgresql+psycopg://receptionist:receptionist@localhost:55432/receptionist_eval
MODE ?= tools
HAS_WEB_DEPS := $(wildcard web/node_modules/.bin/next)

.PHONY: help setup dev down logs db test test-unit lint lint-py lint-web format typecheck check \
        eval seed create-admin agent-dev e2e web-build migrate migration bicep

help:
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

setup: ## Install Python (uv) and web (npm) dependencies
	$(UV) sync --frozen --all-extras
	cd web && npm ci --no-audit --no-fund

dev: ## Start Postgres, API, worker and dashboard (http://localhost:3010)
	$(COMPOSE) up --build

down: ## Stop the stack
	$(COMPOSE) down

logs: ## Tail logs
	$(COMPOSE) logs -f api worker web

db: ## Start only Postgres (for tests)
	$(COMPOSE) up -d db

test: ## Unit + integration tests (needs Postgres: `make db`)
	TEST_DATABASE_URL=$(TEST_DATABASE_URL) $(UV) run pytest

test-unit: ## Unit tests only (no database)
	$(UV) run pytest -m "not integration"

lint: lint-py lint-web ## Lint and type-check Python and TypeScript

lint-py:
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy

lint-web:
ifneq ($(HAS_WEB_DEPS),)
	cd web && npx eslint src && npx next typegen >/dev/null && npx tsc --noEmit
else
	@echo "web/node_modules missing: run 'make setup' to lint the dashboard"
endif

format: ## Auto-format Python
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

typecheck: ## mypy only
	$(UV) run mypy

check: lint test ## Must pass before every commit

eval: ## Run the evaluation (MODE=tools default; MODE=llm needs GEMINI_API_KEY)
	EVAL_DATABASE_URL=$(EVAL_DATABASE_URL) $(UV) run python -m eval.run --mode $(MODE)

seed: ## Load the demo business and synthetic activity into the running stack
	$(COMPOSE) exec api python -m app.seed --demo

create-admin: ## Create the first admin: make create-admin EMAIL=you@example.com
	$(COMPOSE) exec -it api python -m app.cli create-admin --email $(EMAIL)

agent-dev: ## Run the voice agent locally, connected to LiveKit Cloud
	API_URL=$${API_URL:-http://localhost:8010} $(UV) run --extra agent python -m agent.main dev

e2e: ## Playwright end-to-end tests against the running stack
	cd web && npx playwright test

web-build: ## Production build of the dashboard
	cd web && npx next build

migrate: ## Apply migrations
	$(UV) run alembic upgrade head

migration: ## New migration: make migration m="add x"
	$(UV) run alembic revision --autogenerate -m "$(m)"

bicep: ## Validate the Azure infrastructure (needs Azure CLI)
	az bicep build --file deploy/azure/main.bicep --stdout >/dev/null && echo "bicep ok"
