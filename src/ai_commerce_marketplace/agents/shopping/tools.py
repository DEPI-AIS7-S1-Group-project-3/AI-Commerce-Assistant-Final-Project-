"""Tool layer for the Shopping Agent (read-only).

Skeleton: REGISTRY is empty. Person A adds search_products and
categories_brands_list. Person B adds product_get and products_compare.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.exceptions import AppError
from ai_commerce_marketplace.services import catalog_search

MAX_LIMIT = 20


@dataclass(frozen=True)
class ToolContext:
    """Injected by the router from the token. Not visible to the LLM."""

    session: Session
    customer_id: int | None = None  # None = anonymous visitor


class ToolInputError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _limit(value: int) -> int:
    if not isinstance(value, int) or value < 1:
        raise ToolInputError("invalid_limit", "limit must be a positive integer")
    return min(value, MAX_LIMIT)


def _jsonable(obj: Any) -> Any:
    """Turn Pydantic models and Decimals into plain JSON-safe values."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_jsonable(v) for v in obj]
    return obj


def _safe(fn: Callable[[], Any]) -> dict[str, Any]:
    """Run a tool body and always return a dict (never raise to the agent)."""
    try:
        return {"ok": True, **_jsonable(fn())}
    except ToolInputError as e:
        return {"ok": False, "error": e.code, "message": str(e)}
    except AppError as e:
        return {"ok": False, "error": e.code, "message": e.message}


# What the LLM may fill in. ctx is never listed here.
# Each entry: {"fn": callable, "description": str, "params": [names]}
def categories_brands_list(ctx: ToolContext) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        data = catalog_search.list_categories_brands(ctx.session)
        return {**data, "empty": not data["categories"] and not data["brands"]}

    return _safe(run)


REGISTRY: dict[str, dict[str, Any]] = {
    "categories_brands_list": {
        "fn": categories_brands_list,
        "description": "All product categories and brands with their slugs, "
        "used to turn the customer's words into filters.",
        "params": [],
    },
}


def call_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Single entry point for the graph/router. Unknown tools and extra args are rejected."""
    spec = REGISTRY.get(name)
    if spec is None:
        return {"ok": False, "error": "unknown_tool", "message": f"No tool named {name}"}
    extra = set(args) - set(spec["params"])
    if extra:
        # e.g. the model tried to pass customer_id
        return {
            "ok": False,
            "error": "forbidden_argument",
            "message": f"Not allowed: {sorted(extra)}",
        }
    try:
        return spec["fn"](ctx, **args)
    except TypeError:
        return {"ok": False, "error": "bad_arguments", "message": "Missing or wrong arguments"}
