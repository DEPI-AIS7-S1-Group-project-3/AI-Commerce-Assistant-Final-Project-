from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from ai_commerce_marketplace.agents.seller.tools import (
    REGISTRY,
    ToolContext,
    call_tool,
)
from ai_commerce_marketplace.services import seller_analytics as sa
from ai_commerce_marketplace.services.seller_analytics import Period
from tests import factories as f

T0 = datetime(2026, 10, 1, tzinfo=UTC)
FROM, TO = "2026-10-01", "2026-10-31"
P = Period(T0, datetime(2026, 10, 31, tzinfo=UTC))


def _order(session, seller, product, qty, price, status="pending", days=1):
    created = T0 + timedelta(days=days)
    extra = {}
    if status == "cancelled":
        extra["cancelled_at"] = created + timedelta(hours=1)
    o = f.make_order(
        session,
        seller_id=seller.id,
        status=status,
        created_at=created,
        subtotal_egp=price * qty,
        shipping_fee_egp=Decimal("60.00"),
        total_egp=price * qty + Decimal("60.00"),
        **extra,
    )
    f.make_order_item(session, order=o, product=product, qty=qty, unit_price=price)
    return o


@pytest.fixture
def seller(session):
    return f.make_seller(session)


@pytest.fixture
def ctx(session, seller):
    return ToolContext(session=session, seller_id=seller.id)


# ---- numbers match the service ----
def test_sales_summary_matches_service(session, seller, ctx):
    p = f.make_product(session, seller_id=seller.id)
    _order(session, seller, p, 2, Decimal("100.00"))
    r = call_tool(ctx, "get_sales_summary", {"date_from": FROM, "date_to": TO})
    expected = sa.sales_summary(session, seller.id, P)
    assert r["ok"] is True
    assert r["revenue"] == str(expected["revenue"]) == "200.00"
    assert r["orders_count"] == 1
    assert r["empty"] is False


def test_compare_periods_tool(session, seller, ctx):
    p = f.make_product(session, seller_id=seller.id)
    _order(session, seller, p, 1, Decimal("100.00"), days=1)
    _order(session, seller, p, 1, Decimal("150.00"), days=40)
    r = call_tool(
        ctx,
        "compare_periods",
        {
            "a_from": "2026-10-01",
            "a_to": "2026-10-31",
            "b_from": "2026-10-31",
            "b_to": "2026-11-30",
        },
    )
    assert r["ok"] is True
    assert r["revenue"]["delta"] == "50.00"
    assert r["revenue"]["change_pct"] == "50.0"


def test_top_products_and_limit_cap(session, seller, ctx):
    a = f.make_product(session, seller_id=seller.id)
    b = f.make_product(session, seller_id=seller.id)
    _order(session, seller, a, 1, Decimal("10.00"))
    _order(session, seller, b, 5, Decimal("10.00"))
    r = call_tool(ctx, "top_products", {"date_from": FROM, "date_to": TO, "limit": 999})
    assert [x["product_id"] for x in r["products"]] == [b.id, a.id]


def test_low_stock_tool(session, seller, ctx):
    p = f.make_product(session, seller_id=seller.id, stock_qty=0)
    r = call_tool(ctx, "low_stock_products", {"threshold": 5})
    assert [x["product_id"] for x in r["products"]] == [p.id]


def test_orders_by_status_tool(session, seller, ctx):
    p = f.make_product(session, seller_id=seller.id)
    _order(session, seller, p, 1, Decimal("10.00"))
    r = call_tool(ctx, "orders_by_status", {"date_from": FROM, "date_to": TO})
    assert r["by_status"] == {"pending": 1}


# ---- empty and error results are data, not exceptions ----
def test_empty_period_flagged(ctx):
    r = call_tool(ctx, "get_sales_summary", {"date_from": FROM, "date_to": TO})
    assert r["ok"] is True
    assert r["empty"] is True
    assert r["revenue"] == "0.00"


def test_returns_report_empty(ctx):
    r = call_tool(ctx, "returns_report", {"date_from": FROM, "date_to": TO})
    assert r["empty"] is True


# ---- input validation ----
@pytest.mark.parametrize(
    ("args", "code"),
    [
        ({"date_from": "not-a-date", "date_to": TO}, "invalid_date"),
        ({"date_from": TO, "date_to": FROM}, "invalid_period"),
        ({"date_from": "2020-01-01", "date_to": "2026-01-01"}, "period_too_long"),
    ],
)
def test_bad_dates_rejected(ctx, args, code):
    r = call_tool(ctx, "get_sales_summary", args)
    assert r["ok"] is False
    assert r["error"] == code


def test_bad_limit_and_threshold(ctx):
    r = call_tool(ctx, "top_products", {"date_from": FROM, "date_to": TO, "limit": -1})
    assert r["error"] == "invalid_limit"
    r = call_tool(ctx, "low_stock_products", {"threshold": -3})
    assert r["error"] == "invalid_threshold"


def test_missing_args_do_not_raise(ctx):
    r = call_tool(ctx, "get_sales_summary", {"date_from": FROM})
    assert r["ok"] is False
    assert r["error"] == "bad_arguments"


# ---- identity and isolation ----
@pytest.mark.parametrize("forbidden", ["seller_id", "user_id", "session", "ctx"])
def test_llm_cannot_pass_identity(ctx, forbidden):
    r = call_tool(ctx, "get_sales_summary", {"date_from": FROM, "date_to": TO, forbidden: 1})
    assert r["ok"] is False
    assert r["error"] == "forbidden_argument"


def test_unknown_tool(ctx):
    assert call_tool(ctx, "delete_everything", {})["error"] == "unknown_tool"


def test_registry_never_exposes_identity():
    for spec in REGISTRY.values():
        assert not {"seller_id", "ctx", "session"} & set(spec["params"])


def test_seller_only_sees_own_numbers(session, seller, ctx):
    other = f.make_seller(session)
    mine = f.make_product(session, seller_id=seller.id)
    theirs = f.make_product(session, seller_id=other.id)
    _order(session, seller, mine, 1, Decimal("10.00"))
    _order(session, other, theirs, 9, Decimal("999.00"))
    r = call_tool(ctx, "get_sales_summary", {"date_from": FROM, "date_to": TO})
    assert r["revenue"] == "10.00"


def test_other_sellers_product_looks_nonexistent(session, seller, ctx):
    other = f.make_seller(session)
    theirs = f.make_product(session, seller_id=other.id)
    r = call_tool(ctx, "get_product_reviews", {"product_id": theirs.id})
    missing = call_tool(ctx, "get_product_reviews", {"product_id": 999999})
    assert r["ok"] is False
    assert (r["error"], r["message"]) == (missing["error"], missing["message"])
