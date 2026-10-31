.PHONY: help setup test lint format typecheck seed migrate db-reset up down

help:
	@echo Targets: setup test lint format typecheck seed migrate db-reset up down

setup:
	uv sync

test:
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