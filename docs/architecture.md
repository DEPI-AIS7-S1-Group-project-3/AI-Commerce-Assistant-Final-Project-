# Architecture

## Layers

```
routes  ->  services  ->  repositories  ->  models
```

| Layer | Path | Responsibility |
|---|---|---|
| routes | `api/routes/` | HTTP only: parse the request, call a service, return the response. No business logic, no direct DB queries. |
| services | `services/` | All business rules (cart, checkout, order state, eligibility). The AI agents will call these same services later. |
| repositories | `database/repositories/` | All SQL / SQLAlchemy queries. |
| models | `database/models/` | SQLAlchemy table definitions. |

## Import rule

A layer may import only from the layer to its right. Never the reverse.
For example, a repository must not import a service, and a route must not import a model or run a query.

## Identity rule

`customer_id` and `seller_id` always come from the auth token, never from the request body.

## Errors

Every error returns the same shape, with no stack traces:

```json
{ "code": "not_found", "message": "The requested item was not found", "details": null }
```

Every response carries an `X-Request-ID` header (reused from the request if sent, otherwise generated).
Raise `AppError` subclasses (`NotFoundError`, `ForbiddenError`, ...) from services; the handlers in `api/main.py` convert them.

## Running the API

```bash
uv run uvicorn ai_commerce_marketplace.api.main:app --reload
```

Interactive docs: http://localhost:8000/docs
