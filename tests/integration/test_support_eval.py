"""Support Agent eval: 22 questions on the demo data.

Runs on the dev database seeded with --anchor-date 2026-11-04T12:00:00 (same as the other agents'
evals) and skips itself otherwise. The Support tools only read, and each question still runs in a
transaction that is rolled back. Questions marked ``known_gap`` are expected to fail today: they
document what keyword search cannot do yet, and they turn into a failure as soon as search
improves (``xfail(strict=True)``), so the flag has to be removed then.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from ai_commerce_marketplace.agents.support.tools import ToolContext, call_tool
from ai_commerce_marketplace.core.config import settings

QUESTIONS = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "src/ai_commerce_marketplace/agents/support/eval/questions.json"
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
        obj = obj[int(part)] if part.isdigit() else obj[part]
    return obj


def _sections(r):
    return [f"{s['policy_slug']}:{s['section_no']}" for s in r["sections"]]


def _check(r, expect):
    for key, value in expect.items():
        if key == "top":
            assert _sections(r)[0] == value, _sections(r)
        elif key == "top3":
            assert value in _sections(r)[:3], _sections(r)
        elif key == "top3_any":
            assert set(value) & set(_sections(r)[:3]), _sections(r)
        elif key == "empty":
            assert r["empty"] is value
        elif key == "order_ids_include":
            assert set(value) <= {o["order_id"] for o in r["orders"]}
        else:
            assert _dig(r, key) == value, key


def _param(q):
    marks = (
        [pytest.mark.xfail(strict=True, reason="keyword search gap")] if q.get("known_gap") else []
    )
    return pytest.param(q, id=f"q{q['id']}", marks=marks)


@pytest.mark.parametrize("q", [_param(q) for q in QUESTIONS])
def test_tool_answers_match_gold(dev_session, q):
    customer_id = None
    if q["customer"] != "visitor":
        customer_id = dev_session.execute(
            text("SELECT id FROM users WHERE email = :e"), {"e": q["customer"]}
        ).scalar_one()
    ctx = ToolContext(session=dev_session, customer_id=customer_id, now=ANCHOR)

    r = call_tool(ctx, q["tool"], q["args"])

    expect = q["expect"]
    if "error" in expect:
        assert r["ok"] is False
        assert r["error"] == expect["error"]
        return
    assert r["ok"] is True, r
    _check(r, expect)
