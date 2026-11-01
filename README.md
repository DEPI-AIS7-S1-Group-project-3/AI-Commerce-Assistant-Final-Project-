# AI Commerce Marketplace

An Egyptian electronics marketplace (mobiles, laptops, audio & accessories), built as the DEPI AIS7 final project (Group 3).

- **Phase 1 (current):** a complete store with no AI: customers, sellers, catalog, cart, orders, cancellations, returns, reviews and policies.
- **Phase 2 (planned):** AI agents (Shopping, Support, Seller, Order Actions) that call the same services and the same database.

> All data in this project is synthetic and for demo purposes only.

## Tech stack

| Area | Tools |
|---|---|
| Language | Python 3.12+ |
| Database | PostgreSQL 16 (Docker Compose) |
| ORM / migrations | SQLAlchemy 2.0 (typed, sync) + psycopg 3, Alembic |
| Validation / config | Pydantic v2, pydantic-settings |
| API | FastAPI, Uvicorn |
| Auth | JWT (PyJWT), argon2 password hashing |
| Tooling | uv, pytest, ruff, mypy, pre-commit, GitHub Actions |

## Getting started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running)
- [uv](https://docs.astral.sh/uv/) (`pip install uv`)
- Git
- `make` (Windows: `winget install ezwinports.make`)

### Setup

```bash
git clone https://github.com/DEPI-AIS7-S1-Group-project-3/AI-Commerce-Assistant-Final-Project-.git
cd AI-Commerce-Assistant-Final-Project-

cp .env.example .env             # Windows PowerShell: Copy-Item .env.example .env
make setup                       # install dependencies
uv run pre-commit install        # one time per machine
make up                          # start PostgreSQL 16
make migrate                     # create all tables
make seed                        # load demo data
```

Check that the tables exist:

```bash
docker compose exec db psql -U app -d ai_commerce -c "\dt"
```

You should see 15 tables plus `alembic_version`.

### Running the tests

```bash
make test    # starts the db, creates the test database if needed, runs pytest
```

The tests run against a separate database (`ai_commerce_test`) so your development data is never touched.

### Useful migration commands

```bash
uv run alembic upgrade head                          # apply migrations
uv run alembic downgrade base                        # roll everything back
uv run alembic revision --autogenerate -m "message"  # new migration after changing models
uv run alembic check                                 # models and DB must match
```

## Running the API

```bash
uv run uvicorn ai_commerce_marketplace.api.main:app --reload
```

Interactive docs (OpenAPI): http://localhost:8000/docs
Full endpoint reference: [docs/api-contracts.md](docs/api-contracts.md)

## Backend core (M1)

The API is a thin layer over services:

```
routes  ->  services  ->  repositories / models
```

- **Routes** (`api/routes/`): HTTP only, no business logic.
- **Services** (`services/`): all business rules. The AI agents will call these same services.
- Identity (`customer_id`) always comes from the JWT, never from the request body.
- Every error has the same shape `{code, message, details}` and every response carries an `X-Request-ID` header.

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Addresses | CRUD + set default, one default per customer |
| Cart | add / update / remove / clear, stock checked, subtotal computed on the server |
| Checkout | `POST /orders`: one transaction, row locking, stock deduction, one order per seller |
| Orders | list, detail with status timeline, cancel, return |

Key design decisions:

- **Checkout is atomic.** Product rows are locked (`SELECT ... FOR UPDATE`, ordered by id to avoid deadlocks); any failure rolls everything back. A real concurrency test proves two customers racing for the last unit cannot oversell.
- **Prices and addresses are snapshotted** on the order at purchase time.
- **One place changes order status.** `services/order_state.py` validates the transition and writes `order_status_history` (the future audit trail).
- **Eligibility rules are pure functions** (`services/order_rules.py`): cancel only before shipping; return within 14 days of delivery (day 14 accepted, day 15 rejected). The Order Actions Agent will call these instead of deciding by itself.
- **Role is read from the database,** not trusted from the token.

Shipping: 60 EGP per order, free from 5000 EGP. Payment: `cod` is pending, `wallet`/`card` are simulated as paid.

## Quality

```bash
make lint     # ruff check, ruff format --check, mypy
make test     # starts the db, creates the test database if needed, runs pytest
make format   # auto-fix
```

CI (`.github/workflows/backend.yml`) runs the same checks on every pull request against a PostgreSQL service container.
See [docs/development-guide.md](docs/development-guide.md) for setup, configuration and resetting data.

## Project structure

```
src/ai_commerce_marketplace/
  api/           main.py (app factory), dependencies.py, routes/
  core/          config.py, security.py, exceptions.py, enums.py
  database/      base.py, session.py, models/
  schemas/       request/response models (auth, address, cart, order, specs)
  services/      auth, addresses, cart, checkout, orders, order_state, order_rules, order_actions
  nlp/           Arabic text normalization for search
migrations/      Alembic environment and versions
tests/           pytest suite (real PostgreSQL)
docs/            architecture.md, api-contracts.md, development-guide.md
.github/         CI workflow (ruff, mypy, pytest)
docker-compose.yml
```

## Database

15 tables:

| Group | Tables |
|---|---|
| Identity | `users`, `addresses`, `sellers` |
| Catalog | `categories`, `brands`, `products`, `product_images` |
| Cart | `carts`, `cart_items` |
| Orders | `orders`, `order_items`, `order_status_history`, `returns` |
| Content | `reviews`, `policies` |

Key design decisions:

- Integer IDs (`GENERATED BY DEFAULT AS IDENTITY`); orders start at 10001.
- Money is `NUMERIC(12,2)` in EGP, columns are named `*_egp`.
- Timestamps are `timestamptz` (UTC).
- Enums are `text` + `CHECK` constraints, generated from a single source in `core/enums.py`.
- Product specs live in a `JSONB` column; Arabic search uses `pg_trgm`.
- One order belongs to one seller; a checkout with several sellers becomes several orders sharing a `checkout_group_id`.
- Purchase price and shipping address are snapshotted on the order.
- Products are soft-deleted (`is_active = false`).

## Git workflow

- Never commit directly to `main`. Branch from it and open a pull request.
- Branch names: `feat/...`, `fix/...`, `test/...`, `docs/...`, `chore/...`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/), for example `feat(db): add product model`.
- After a migration is merged, never edit it. Add a new migration instead.
- Run `make lint` and `make test` before opening a PR; CI runs the same checks.
