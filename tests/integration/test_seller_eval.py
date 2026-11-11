import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from ai_commerce_marketplace.agents.seller.tools import ToolContext, call_tool
from ai_commerce_marketplace.core.config import settings

QUESTIONS = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "src/ai_commerce_marketplace/agents/seller/eval/questions.json"
    ).read_text(encoding="utf-8")
)

DEV_URL = settings.database_url.replace("/ai_commerce_test", "/ai_commerce")


@pytest.fixture(scope="module")
def dev_session():
    engine = create_engine(DEV_URL)
    with Session(engine) as s:
        try:
            last = s.execute(text("SELECT MAX(created_at)::date FROM orders")).scalar()
        except Exception:
            pytest.skip("dev database not available")
        if str(last) != "2026-11-04":
            pytest.skip("dev DB is not seeded with --anchor-date 2026-11-04T12:00:00")
        yield s
    engine.dispose()


def _dig(obj, dotted):
    for part in dotted.split("."):
        obj = obj[part]
    return obj


@pytest.mark.parametrize("q", QUESTIONS, ids=[f"q{q['id']}" for q in QUESTIONS])
def test_tool_answers_match_gold(dev_session, q):
    ctx = ToolContext(session=dev_session, seller_id=q["seller"])
    r = call_tool(ctx, q["tool"], q["args"])
    exp = q["expect"]

    if "error" in exp:
        assert r["ok"] is False
        assert r["error"] == exp["error"]
        return

    assert r["ok"] is True, r
    for key, value in exp.items():
        if key == "product_ids":
            assert [p["product_id"] for p in r["products"]] == value
        elif key == "empty":
            assert r["empty"] is value
        elif key == "by_reason":
            assert r["by_reason"] == value
        elif "." in key:
            assert str(_dig(r, key)) == value, key
        else:
            got = r[key]
            assert (str(got) if isinstance(value, str) else got) == value, key
