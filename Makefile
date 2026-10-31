.PHONY: help setup test test-db lint format typecheck seed migrate db-reset up down

help:
	@echo Targets: setup test test-db lint format typecheck seed migrate db-reset up down

setup:
	uv sync

test-db:
	docker compose up -d db
	-docker compose exec -T db psql -U app -d ai_commerce -c "CREATE DATABASE ai_commerce_test"

test: test-db
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src

format:
	uv run ruff check . --fix
	uv run ruff format .

typecheck:
	uv run mypy src

seed:
	uv run python -m scripts.seed_database

migrate:
	uv run alembic upgrade head

db-reset:
	uv run alembic downgrade base
	uv run alembic upgrade head

up:
	docker compose up -d

down:
	docker compose down
