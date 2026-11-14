"""Order Actions Agent eval: 15 questions on the demo data.

Runs on the dev database seeded with --anchor-date 2026-11-04T12:00:00 (same as the seller eval).
Every question runs inside a transaction that is rolled back, so cancels and returns leave no trace.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from ai_commerce_marketplace.agents.order_actions.tools import (
    ToolContext,
    call_tool,
    execute_confirmed,
)
from ai_commerce_marketplace.core.config import settings

QUESTIONS = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "src/ai_commerce_marketplace/agents/order_actions/eval/questions.json"
    ).read_text(encoding="utf-8")
)

DEV_URL = settings.database_url.replace("/ai_commerce_test", "/ai_commerce")
ANCHOR = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def dev_engine():
    engine = create_engine(DEV_URL)
    try:
        with engine.connect() as conn:
            last = conn.execute(text("SELECT MAX(created_at)::date FROM orders")).scalar()
    except Exception:
        pytest.skip("dev database not available")
    if str(last) != "2026-11-04":
        pytest.skip("dev DB is not seeded with --anchor-date 2026-11-04T12:00:00")
    yield engine
    engine.dispose()


@pytest.fixture
def dev_session(dev_engine):
    with dev_engine.connect() as conn:
        outer = conn.begin()
        s = Session(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield s
        finally:
            s.close()
            outer.rollback()


def _dig(obj, dotted):
    for part in dotted.split("."):
        obj = obj[part]
    return obj


@pytest.mark.parametrize("q", QUESTIONS, ids=[f"q{q['id']}" for q in QUESTIONS])
def test_tool_answers_match_gold(dev_session, q):
    customer_id = dev_session.execute(
        text("SELECT id FROM users WHERE email = :e"), {"e": q["customer"]}
    ).scalar_one()
    ctx = ToolContext(session=dev_session, customer_id=customer_id, now=ANCHOR)

    args = dict(q["args"])
    if args.get("order_item_id") == "$item":  # item ids are not fixed in the seed
        order = call_tool(ctx, "get_order", {"order_id": args["order_id"]})["order"]
        args["order_item_id"] = order["items"][0]["order_item_id"]

    r = call_tool(ctx, q["tool"], args)
    if q.get("confirm"):
        assert r.get("needs_confirmation") is True, r
        r = {**r, "after": execute_confirmed(ctx, r["pending_action"])}

    exp = q["expect"]
    if "error" in exp:
        assert r["ok"] is False
        assert r["error"] == exp["error"]
        assert r["message_ar"]
        return

    assert r["ok"] is True, r
    for key, value in exp.items():
        if key == "order_ids_include":
            assert set(value) <= {o["id"] for o in r["orders"]}
        else:
            assert _dig(r, key) == value, key
