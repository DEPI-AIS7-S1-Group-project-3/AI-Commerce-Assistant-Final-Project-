"""Shared building blocks for the agent tool layers (Seller, Shopping, Support, ...).

Every agent exposes the same contract to the graph/router:

- a ``REGISTRY`` of tools: ``{name: {"fn", "description", "params"}}``;
- a ``ToolContext`` injected by the router from the token (never visible to the LLM);
- one entry point, ``call_tool(registry, ctx, name, args)``.

Guarantees of ``call_tool`` (the agent can rely on them):

- an unknown tool is rejected (``unknown_tool``);
- an argument that is not listed in the tool's ``params`` is rejected (``forbidden_argument``),
  for example when the model tries to pass ``customer_id`` or ``seller_id``;
- a missing or misspelled argument is rejected before the tool runs (``bad_arguments``);
- expected failures (``ToolInputError`` and ``AppError``) come back as data
  ``{"ok": False, "error": code, "message": ...}``, never as an exception.
"""

import inspect
from collections.abc import Callable, Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from ai_commerce_marketplace.core.exceptions import AppError

MAX_LIMIT = 20

ToolRegistry = Mapping[str, Mapping[str, Any]]


class ToolInputError(ValueError):
    """The model passed a value a tool cannot accept. Returned to the agent as data."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def clamp_limit(value: Any, maximum: int = MAX_LIMIT) -> int:
    """A positive integer, capped at ``maximum``. Bools are rejected."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ToolInputError("invalid_limit", "limit must be a positive integer")
    return min(value, maximum)


def positive_id(value: Any, *, code: str, name: str) -> int:
    """Accept 12 or "12"; reject bools, floats, other text and non-positive numbers."""
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ToolInputError(code, f"Not a valid {name}: {value!r}")
    return value


def jsonable(obj: Any) -> Any:
    """Turn Pydantic models, Decimals and dates into plain JSON-safe values."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime | date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [jsonable(v) for v in obj]
    return obj


def safe(fn: Callable[[], Any]) -> dict[str, Any]:
    """Run a tool body and always return a dict for expected failures."""
    try:
        return {"ok": True, **jsonable(fn())}
    except ToolInputError as e:
        return {"ok": False, "error": e.code, "message": str(e)}
    except AppError as e:
        return {"ok": False, "error": e.code, "message": e.message}


def call_tool(registry: ToolRegistry, ctx: Any, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Single entry point for the graph/router."""
    spec = registry.get(name)
    if spec is None:
        return {"ok": False, "error": "unknown_tool", "message": f"No tool named {name}"}

    allowed = set(spec["params"])
    extra = set(args) - allowed
    if extra:
        return {
            "ok": False,
            "error": "forbidden_argument",
            "message": f"Not allowed: {sorted(extra)}",
        }

    fn = spec["fn"]
    try:
        # Check the call shape up front, so a real TypeError inside a tool is not hidden
        # behind a generic "bad arguments" answer.
        inspect.signature(fn).bind(ctx, **args)
    except TypeError:
        return {"ok": False, "error": "bad_arguments", "message": "Missing or wrong arguments"}
    result: dict[str, Any] = fn(ctx, **args)
    return result
