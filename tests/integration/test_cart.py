from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from ai_commerce_marketplace.api.main import create_app
from ai_commerce_marketplace.core.security import create_access_token
from ai_commerce_marketplace.database.session import get_session
from tests import factories as f


@pytest.fixture
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def user(session):
    return f.make_user(session)


def _h(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def _add(client, user, product, qty=1):
    return client.post("/cart/items", json={"product_id": product.id, "qty": qty}, headers=_h(user))


# ---- happy path ----
def test_empty_cart(client, user):
    r = client.get("/cart", headers=_h(user))
    assert r.status_code == 200
    assert r.json() == {"items": [], "subtotal_egp": "0.00"}


def test_add_and_view_with_server_subtotal(client, session, user):
    p1 = f.make_product(session, price_egp=Decimal("1000.00"))
    p2 = f.make_product(session, price_egp=Decimal("250.50"))
    _add(client, user, p1, 2)
    r = _add(client, user, p2, 3)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    # 2*1000.00 + 3*250.50 = 2751.50
    assert Decimal(body["subtotal_egp"]) == Decimal("2751.50")
    assert Decimal(body["items"][0]["line_total_egp"]) == Decimal("2000.00")


# ---- edge cases ----
def test_adding_same_product_merges_into_one_line(client, session, user):
    p = f.make_product(session)
    _add(client, user, p, 2)
    r = _add(client, user, p, 3)
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["qty"] == 5


def test_qty_equal_to_stock_is_allowed(client, session, user):
    p = f.make_product(session, stock_qty=4)
    assert _add(client, user, p, 4).status_code == 200


def test_set_qty_updates_line(client, session, user):
    p = f.make_product(session)
    _add(client, user, p, 1)
    r = client.put(f"/cart/items/{p.id}", json={"qty": 7}, headers=_h(user))
    assert r.status_code == 200
    assert r.json()["items"][0]["qty"] == 7


def test_remove_item(client, session, user):
    p = f.make_product(session)
    _add(client, user, p)
    r = client.delete(f"/cart/items/{p.id}", headers=_h(user))
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_clear_cart(client, session, user):
    _add(client, user, f.make_product(session))
    _add(client, user, f.make_product(session))
    r = client.delete("/cart", headers=_h(user))
    assert r.status_code == 200
    assert r.json() == {"items": [], "subtotal_egp": "0.00"}


def test_clear_empty_cart_is_ok(client, user):
    assert client.delete("/cart", headers=_h(user)).status_code == 200


# ---- stock failures ----
def test_qty_above_stock_rejected(client, session, user):
    p = f.make_product(session, stock_qty=3)
    r = _add(client, user, p, 4)
    assert r.status_code == 400
    assert r.json()["code"] == "insufficient_stock"
    assert r.json()["details"]["available"] == 3


def test_merged_qty_above_stock_rejected(client, session, user):
    p = f.make_product(session, stock_qty=5)
    _add(client, user, p, 3)
    r = _add(client, user, p, 3)  # 3 + 3 = 6 > 5
    assert r.status_code == 400
    assert r.json()["code"] == "insufficient_stock"
    # the existing line is unchanged
    assert client.get("/cart", headers=_h(user)).json()["items"][0]["qty"] == 3


def test_set_qty_above_stock_rejected(client, session, user):
    p = f.make_product(session, stock_qty=5)
    _add(client, user, p, 1)
    r = client.put(f"/cart/items/{p.id}", json={"qty": 6}, headers=_h(user))
    assert r.status_code == 400


def test_out_of_stock_product_rejected(client, session, user):
    p = f.make_product(session, stock_qty=0)
    assert _add(client, user, p, 1).status_code == 400


# ---- product failures ----
def test_inactive_product_rejected(client, session, user):
    p = f.make_product(session, is_active=False)
    r = _add(client, user, p)
    assert r.status_code == 404
    assert r.json()["code"] == "product_not_found"


def test_unknown_product_rejected(client, user):
    r = client.post("/cart/items", json={"product_id": 999999, "qty": 1}, headers=_h(user))
    assert r.status_code == 404


# ---- validation ----
@pytest.mark.parametrize("qty", [0, -1, 101])
def test_bad_qty_422(client, session, user, qty):
    p = f.make_product(session)
    r = client.post("/cart/items", json={"product_id": p.id, "qty": qty}, headers=_h(user))
    assert r.status_code == 422


def test_set_qty_zero_422(client, session, user):
    p = f.make_product(session)
    _add(client, user, p)
    r = client.put(f"/cart/items/{p.id}", json={"qty": 0}, headers=_h(user))
    assert r.status_code == 422


def test_set_or_remove_missing_line_404(client, session, user):
    p = f.make_product(session)
    put = client.put(f"/cart/items/{p.id}", json={"qty": 1}, headers=_h(user))
    delete = client.delete(f"/cart/items/{p.id}", headers=_h(user))
    assert put.status_code == 404
    assert delete.status_code == 404


def test_requires_login(client):
    assert client.get("/cart").status_code == 401
    assert client.post("/cart/items", json={"product_id": 1, "qty": 1}).status_code == 401
    assert client.delete("/cart").status_code == 401


# ---- availability flag ----
def test_deactivated_product_flagged_and_excluded_from_subtotal(client, session, user):
    keep = f.make_product(session, price_egp=Decimal("100.00"))
    gone = f.make_product(session, price_egp=Decimal("500.00"))
    _add(client, user, keep, 1)
    _add(client, user, gone, 1)

    gone.is_active = False
    session.flush()

    body = client.get("/cart", headers=_h(user)).json()
    flags = {i["product_id"]: i["available"] for i in body["items"]}
    assert flags == {keep.id: True, gone.id: False}
    assert Decimal(body["subtotal_egp"]) == Decimal("100.00")


def test_stock_drop_flags_line_unavailable(client, session, user):
    p = f.make_product(session, stock_qty=5, price_egp=Decimal("100.00"))
    _add(client, user, p, 4)

    p.stock_qty = 2
    session.flush()

    body = client.get("/cart", headers=_h(user)).json()
    assert body["items"][0]["available"] is False
    assert Decimal(body["subtotal_egp"]) == Decimal("0.00")


def test_deactivated_product_can_still_be_removed(client, session, user):
    p = f.make_product(session)
    _add(client, user, p)
    p.is_active = False
    session.flush()
    r = client.delete(f"/cart/items/{p.id}", headers=_h(user))
    assert r.status_code == 200
    assert r.json()["items"] == []


# ---- isolation ----
def test_carts_are_isolated_between_customers(client, session):
    a = f.make_user(session)
    b = f.make_user(session)
    p = f.make_product(session)
    _add(client, a, p, 2)

    assert client.get("/cart", headers=_h(b)).json()["items"] == []
    # b cannot edit or remove a's line
    assert client.put(f"/cart/items/{p.id}", json={"qty": 1}, headers=_h(b)).status_code == 404
    assert client.delete(f"/cart/items/{p.id}", headers=_h(b)).status_code == 404
    # a's cart is untouched
    assert client.get("/cart", headers=_h(a)).json()["items"][0]["qty"] == 2


def test_user_id_in_body_is_ignored(client, session):
    owner = f.make_user(session)
    victim = f.make_user(session)
    p = f.make_product(session)
    r = client.post(
        "/cart/items",
        json={"product_id": p.id, "qty": 1, "user_id": victim.id},
        headers=_h(owner),
    )
    assert r.status_code == 200
    assert client.get("/cart", headers=_h(victim)).json()["items"] == []
    assert len(client.get("/cart", headers=_h(owner)).json()["items"]) == 1
