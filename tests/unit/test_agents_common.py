from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import BaseModel

from ai_commerce_marketplace.agents.common import (
    ToolInputError,
    call_tool,
    clamp_limit,
    jsonable,
    positive_id,
    safe,
)
from ai_commerce_marketplace.core.exceptions import NotFoundError


class Ctx:
    """Stands in for a ToolContext; the generic call_tool does not look inside it."""

    customer_id = 7


def echo(ctx: Ctx, value: int) -> dict:
    return {"ok": True, "value": value, "customer_id": ctx.customer_id}


def no_args(ctx: Ctx) -> dict:
    return {"ok": True}


def broken(ctx: Ctx, value: int) -> dict:
    return {"ok": True, "x": value + "text"}  # type: ignore[operator]  # a real bug inside a tool


REGISTRY = {
    "echo": {"fn": echo, "description": "Echo a value.", "params": ["value"]},
    "no_args": {"fn": no_args, "description": "No arguments.", "params": []},
    "broken": {"fn": broken, "description": "Has a bug.", "params": ["value"]},
}


# ---- call_tool ----
def test_call_tool_runs_a_listed_tool():
    r = call_tool(REGISTRY, Ctx(), "echo", {"value": 3})
    assert r == {"ok": True, "value": 3, "customer_id": 7}


def test_unknown_tool_is_rejected():
    r = call_tool(REGISTRY, Ctx(), "nope", {})
    assert r["ok"] is False and r["error"] == "unknown_tool"


@pytest.mark.parametrize("forbidden", ["customer_id", "seller_id", "ctx", "session"])
def test_identity_arguments_are_rejected(forbidden):
    r = call_tool(REGISTRY, Ctx(), "echo", {"value": 1, forbidden: 99})
    assert r["ok"] is False and r["error"] == "forbidden_argument"
    assert forbidden in r["message"]


def test_missing_argument_is_bad_arguments():
    r = call_tool(REGISTRY, Ctx(), "echo", {})
    assert r["ok"] is False and r["error"] == "bad_arguments"


def test_a_tool_without_params_accepts_an_empty_call():
    assert call_tool(REGISTRY, Ctx(), "no_args", {})["ok"] is True


def test_a_real_bug_inside_a_tool_is_not_hidden_as_bad_arguments():
    with pytest.raises(TypeError):
        call_tool(REGISTRY, Ctx(), "broken", {"value": 1})


# ---- safe ----
def test_safe_wraps_a_result():
    assert safe(lambda: {"n": 1}) == {"ok": True, "n": 1}


def test_safe_turns_tool_input_errors_into_data():
    def run():
        raise ToolInputError("invalid_thing", "bad thing")

    assert safe(run) == {"ok": False, "error": "invalid_thing", "message": "bad thing"}


def test_safe_turns_app_errors_into_data():
    def run():
        raise NotFoundError("Order not found", code="order_not_found")

    assert safe(run) == {"ok": False, "error": "order_not_found", "message": "Order not found"}


def test_safe_does_not_swallow_unexpected_errors():
    def run():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        safe(run)


# ---- jsonable ----
class Row(BaseModel):
    price: Decimal
    at: datetime


def test_jsonable_converts_models_decimals_and_dates():
    at = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
    out = jsonable(
        {"row": Row(price=Decimal("10.50"), at=at), "d": Decimal("1.00"), "day": date(2026, 11, 18)}
    )
    assert out["row"]["price"] == "10.50"
    assert out["row"]["at"].startswith("2026-11-18T12:00:00")
    assert out["d"] == "1.00"
    assert out["day"] == "2026-11-18"


def test_jsonable_walks_lists_and_tuples():
    assert jsonable([Decimal("1"), (Decimal("2"),)]) == ["1", ["2"]]


# ---- clamp_limit / positive_id ----
@pytest.mark.parametrize(("value", "expected"), [(1, 1), (5, 5), (20, 20), (500, 20)])
def test_clamp_limit(value, expected):
    assert clamp_limit(value) == expected


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "3", None])
def test_clamp_limit_rejects_bad_values(value):
    with pytest.raises(ToolInputError) as e:
        clamp_limit(value)
    assert e.value.code == "invalid_limit"


@pytest.mark.parametrize(("value", "expected"), [(12, 12), ("12", 12), (" 7 ", 7)])
def test_positive_id_accepts_numbers_and_digit_strings(value, expected):
    assert positive_id(value, code="invalid_order_id", name="order id") == expected


@pytest.mark.parametrize("value", [0, -3, True, 1.5, "abc", "", None, [1]])
def test_positive_id_rejects_everything_else(value):
    with pytest.raises(ToolInputError) as e:
        positive_id(value, code="invalid_order_id", name="order id")
    assert e.value.code == "invalid_order_id"
