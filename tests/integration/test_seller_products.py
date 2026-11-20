from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from ai_commerce_marketplace.api.main import create_app
from ai_commerce_marketplace.core.security import create_access_token
from ai_commerce_marketplace.database.models import User
from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.nlp.arabic import build_search_text
from tests import factories as f


@pytest.fixture
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def seller(session):
    return f.make_seller(session)


@pytest.fixture
def h(session, seller):
    user = session.get(User, seller.user_id)
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def _ids(r):
    assert r.status_code == 200, r.text
    return [p["id"] for p in r.json()]


def test_list_only_own_products_with_filters(client, session, seller, h):
    ok = f.make_product(session, seller_id=seller.id, stock_qty=50)
    low = f.make_product(session, seller_id=seller.id, stock_qty=3)
    out = f.make_product(session, seller_id=seller.id, stock_qty=0)
    hidden = f.make_product(session, seller_id=seller.id, is_active=False)
    f.make_product(session)  # another seller

    assert set(_ids(client.get("/seller/products", headers=h))) == {
        ok.id,
        low.id,
        out.id,
        hidden.id,
    }
    # low = visible with stock <= 5, incl. 0 (same as the dashboard); lowest stock first
    assert _ids(client.get("/seller/products?filter=low", headers=h)) == [out.id, low.id]
    assert _ids(client.get("/seller/products?filter=out", headers=h)) == [out.id]
    assert _ids(client.get("/seller/products?filter=hidden", headers=h)) == [hidden.id]


def test_search_by_text_or_sku(client, session, seller, h):
    p = f.make_product(session, seller_id=seller.id, search_text=build_search_text("شاحن سريع"))
    f.make_product(session, seller_id=seller.id, search_text=build_search_text("لابتوب"))
    assert _ids(client.get("/seller/products?q=شاحن", headers=h)) == [p.id]
    assert _ids(client.get(f"/seller/products?q={p.sku}", headers=h)) == [p.id]


def test_patch_price_stock_visibility(client, session, seller, h):
    p = f.make_product(session, seller_id=seller.id, price_egp=Decimal("1000.00"), stock_qty=5)
    r = client.patch(
        f"/seller/products/{p.id}",
        json={
            "price_egp": "900.00",
            "old_price_egp": "1100.00",
            "stock_qty": 12,
            "is_active": False,
        },
        headers=h,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["price_egp"], body["old_price_egp"]) == ("900.00", "1100.00")
    assert body["stock_qty"] == 12 and body["is_active"] is False


def test_patch_only_changes_sent_fields_and_null_removes_old_price(client, session, seller, h):
    p = f.make_product(
        session, seller_id=seller.id, price_egp=Decimal("1000.00"), old_price_egp=Decimal("1200.00")
    )
    r = client.patch(f"/seller/products/{p.id}", json={"stock_qty": 7}, headers=h)
    assert r.json()["old_price_egp"] == "1200.00" and r.json()["stock_qty"] == 7

    r = client.patch(f"/seller/products/{p.id}", json={"old_price_egp": None}, headers=h)
    assert r.json()["old_price_egp"] is None


def test_old_price_must_be_higher(client, session, seller, h):
    p = f.make_product(session, seller_id=seller.id, price_egp=Decimal("1000.00"))
    r = client.patch(f"/seller/products/{p.id}", json={"old_price_egp": "900.00"}, headers=h)
    assert r.status_code == 400
    assert r.json()["code"] == "invalid_old_price"


@pytest.mark.parametrize(
    "body", [{"price_egp": "0"}, {"stock_qty": -1}, {"price_egp": "abc"}, {"price_egp": "1.234"}]
)
def test_bad_values_are_422(client, session, seller, h, body):
    p = f.make_product(session, seller_id=seller.id)
    assert client.patch(f"/seller/products/{p.id}", json=body, headers=h).status_code == 422


def test_cannot_touch_other_sellers_product(client, session, h):
    other = f.make_product(session)
    r = client.patch(f"/seller/products/{other.id}", json={"stock_qty": 1}, headers=h)
    assert r.status_code == 404


def test_customers_cannot_use_seller_products(client, session):
    user = f.make_user(session)
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    assert client.get("/seller/products", headers=headers).status_code == 403
