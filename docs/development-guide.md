# Development Guide

## First-time setup

```bash
git clone https://github.com/DEPI-AIS7-S1-Group-project-3/AI-Commerce-Assistant-Final-Project-.git
cd AI-Commerce-Assistant-Final-Project-
cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
make setup                  # install dependencies
uv run pre-commit install   # one time per machine
make up                     # start PostgreSQL (waits for the healthcheck)
make migrate                # create all tables
make seed                   # load demo data
make test                   # runs tests (creates ai_commerce_test if missing)
```

## Daily commands

| Command | What it does |
|---|---|
| `make lint` | ruff check, ruff format --check, mypy |
| `make format` | auto-fix with ruff |
| `make test` | start db, create test db if needed, run pytest |
| `make up` / `make down` | start / stop the containers |

## Configuration

Settings are read from environment variables or `.env` (see `.env.example`):

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | required |
| `JWT_SECRET` | signing key for auth tokens | `dev-only-change-me-not-for-production-use` (development only) |
| `CORS_ORIGINS` | allowed frontend origins (JSON list) | `["http://localhost:5173"]` |
| `ENV` | `development` or `production` | `development` |

Never commit a real `.env` or a real secret. All data in this project is synthetic.

## Resetting your data

Reset the development database (keeps the container):

```bash
make db-reset   # downgrade to base, then upgrade to head
make seed       # reload demo data
```

Full wipe, including the Docker volume:

```bash
docker compose down -v
make up
make migrate
make seed
```

## Troubleshooting

- `failed to connect to the docker API`: Docker Desktop is not running. Start it and wait for "Engine running".
- `database "ai_commerce_test" does not exist`: run `make test`; the `test-db` target creates it.
- `missing separator` in the Makefile: indentation must be tabs, not spaces.
