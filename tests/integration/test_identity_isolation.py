import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from ai_commerce_marketplace.api.dependencies import require_role
from ai_commerce_marketplace.api.main import create_app
from ai_commerce_marketplace.core.security import create_access_token
from ai_commerce_marketplace.database.models.user import User
from ai_commerce_marketplace.database.session import get_session
from tests import factories as f

SELLER_ONLY = Depends(require_role("seller"))

ADDR = {
    "recipient_name": "Ahmed Ali",
    "phone": "01012345678",
    "governorate": "Cairo",
    "city": "Nasr City",
    "street_address": "10 Example St",
}


@pytest.fixture
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session

    @app.get("/_seller-only")
    def seller_only(user: User = SELLER_ONLY):
        return {"id": user.id}

    return TestClient(app, raise_server_exceptions=False)


def _h(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


# (method, path, json) for every protected endpoint that does not need real ids
PROTECTED = [
    ("GET", "/auth/me", None),
    ("GET", "/addresses", None),
    ("POST", "/addresses", ADDR),
    ("PUT", "/addresses/1", ADDR),
    ("POST", "/addresses/1/default", None),
    ("DELETE", "/addresses/1", None),
    ("GET", "/cart", None),
    ("POST", "/cart/items", {"product_id": 1, "qty": 1}),
    ("PUT", "/cart/items/1", {"qty": 1}),
    ("DELETE", "/cart/items/1", None),
    ("DELETE", "/cart", None),
    ("POST", "/orders", {"address_id": 1, "payment_method": "cod"}),
    ("GET", "/orders", None),
    ("GET", "/orders/10001", None),
    ("POST", "/orders/10001/cancel", None),
    ("POST", "/orders/10001/items/1/return", {"reason_code": "other"}),
    ("GET", "/_seller-only", None),
]


@pytest.mark.parametrize(("method", "path", "body"), PROTECTED)
def test_no_token_is_401(client, method, path, body):
    r = client.request(method, path, json=body)
    assert r.status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), PROTECTED)
def test_garbage_token_is_401(client, method, path, body):
    r = client.request(method, path, json=body, headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_customer_gets_403_on_seller_route(client, session):
    customer = f.make_user(session)
    assert client.get("/_seller-only", headers=_h(customer)).status_code == 403


# ---- another customer's data is never reachable ----
def test_other_customer_cannot_touch_my_address(client, session):
    owner, other = f.make_user(session), f.make_user(session)
    a = f.make_address(session, owner)
    session.commit()
    for method, path, body in [
        ("PUT", f"/addresses/{a.id}", ADDR),
        ("POST", f"/addresses/{a.id}/default", None),
        ("DELETE", f"/addresses/{a.id}", None),
    ]:
        r = client.request(method, path, json=body, headers=_h(other))
        assert r.status_code == 404, (method, path)


def test_other_customer_cannot_touch_my_order(client, session):
    owner, other = f.make_user(session), f.make_user(session)
    order = f.make_order(session, customer_id=owner.id)
    item = f.make_order_item(session, order=order)
    session.commit()
    for method, path, body in [
        ("GET", f"/orders/{order.id}", None),
        ("POST", f"/orders/{order.id}/cancel", None),
        ("POST", f"/orders/{order.id}/items/{item.id}/return", {"reason_code": "other"}),
    ]:
        r = client.request(method, path, json=body, headers=_h(other))
        assert r.status_code == 404, (method, path)
    assert client.get("/orders", headers=_h(other)).json() == []


def test_cannot_checkout_with_other_customers_address(client, session):
    owner, other = f.make_user(session), f.make_user(session)
    addr = f.make_address(session, owner)
    product = f.make_product(session)
    client.post("/cart/items", json={"product_id": product.id, "qty": 1}, headers=_h(other))
    r = client.post(
        "/orders",
        json={"address_id": addr.id, "payment_method": "cod"},
        headers=_h(other),
    )
    assert r.status_code == 404


# ---- identity comes from the token, never the body ----
def test_body_user_id_is_ignored_on_address_create(client, session):
    me, victim = f.make_user(session), f.make_user(session)
    r = client.post("/addresses", json={**ADDR, "user_id": victim.id}, headers=_h(me))
    assert r.status_code == 201
    assert client.get("/addresses", headers=_h(victim)).json() == []


def test_body_ids_are_ignored_on_cart_and_checkout(client, session):
    me, victim = f.make_user(session), f.make_user(session)
    addr = f.make_address(session, me)
    product = f.make_product(session)
    r = client.post(
        "/cart/items",
        json={"product_id": product.id, "qty": 1, "user_id": victim.id, "customer_id": victim.id},
        headers=_h(me),
    )
    assert r.status_code == 200
    assert client.get("/cart", headers=_h(victim)).json()["items"] == []

    r = client.post(
        "/orders",
        json={
            "address_id": addr.id,
            "payment_method": "cod",
            "customer_id": victim.id,
            "seller_id": 999,
        },
        headers=_h(me),
    )
    assert r.status_code == 201
    assert client.get("/orders", headers=_h(victim)).json() == []
    assert len(client.get("/orders", headers=_h(me)).json()) == 1


def test_forged_role_in_token_does_not_grant_seller_access(client, session):
    customer = f.make_user(session)
    forged = create_access_token(customer.id, "seller")  # token claims seller
    r = client.get("/_seller-only", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 403  # role is read from the DB, not the token
