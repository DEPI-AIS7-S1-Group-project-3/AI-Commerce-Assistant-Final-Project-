"""Shopping Agent eval: each question's tool call is run on the frozen demo data.

Questions name products by SKU (ids depend on insert order); the test turns them into ids:
``product_sku`` -> ``product_id`` and ``product_skus`` (+ ``extra_ids``) -> ``product_ids``.
Needs the dev database seeded with ``--anchor-date 2026-11-04T12:00:00``.
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from ai_commerce_marketplace.agents.shopping.tools import ToolContext, call_tool
from ai_commerce_marketplace.core.config import settings
from ai_commerce_marketplace.database.models import Product

QUESTIONS = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "src/ai_commerce_marketplace/agents/shopping/eval/questions.json"
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


@pytest.fixture(scope="module")
def sku_ids(dev_session):
    return dict(dev_session.execute(select(Product.sku, Product.id)).all())


def _args(raw: dict, sku_ids: dict[str, int]) -> dict:
    args = dict(raw)
    if "product_sku" in args:
        args["product_id"] = sku_ids[args.pop("product_sku")]
    if "product_skus" in args:
        ids = [sku_ids[s] for s in args.pop("product_skus")]
        args["product_ids"] = ids + args.pop("extra_ids", [])
    return args


def _dig(obj, dotted):
    for part in dotted.split("."):
        obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj


@pytest.mark.parametrize("q", QUESTIONS, ids=[f"q{q['id']}" for q in QUESTIONS])
def test_tool_answers_match_gold(dev_session, sku_ids, q):
    ctx = ToolContext(session=dev_session)
    r = call_tool(ctx, q["tool"], _args(q["args"], sku_ids))
    exp = q["expect"]

    if "error" in exp:
        assert r["ok"] is False, r
        assert r["error"] == exp["error"]
        return

    assert r["ok"] is True, r
    id_skus = {v: k for k, v in sku_ids.items()}
    for key, value in exp.items():
        if key == "skus":
            assert [id_skus[p["id"]] for p in r["products"]] == value
        elif key == "positive_count":
            assert len(r["positive"]) == value
        elif key == "negative_count":
            assert len(r["negative"]) == value
        elif key == "category_slugs":
            assert sorted(c["slug"] for c in r["categories"]) == sorted(value)
        elif key == "brand_count":
            assert len(r["brands"]) == value
        elif "." in key:
            assert str(_dig(r, key)) == value, key
        else:
            got = r[key]
            assert (str(got) if isinstance(value, str) else got) == value, key
