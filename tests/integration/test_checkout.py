import threading
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ai_commerce_marketplace.api.main import create_app
from ai_commerce_marketplace.core.security import create_access_token
from ai_commerce_marketplace.database.models.cart import Cart, CartItem
from ai_commerce_marketplace.database.models.catalog import Product
from ai_commerce_marketplace.database.models.order import (
    Order,
    OrderItem,
    OrderStatusHistory,
)
from ai_commerce_marketplace.database.session import engine, get_session
from ai_commerce_marketplace.services.checkout import (
    FREE_SHIPPING_THRESHOLD_EGP,
    SHIPPING_FEE_EGP,
    checkout,
    shipping_fee,
)
from tests import factories as f


@pytest.fixture
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def user(session):
    return f.make_user(session)


@pytest.fixture
def address(session, user):
    return f.make_address(session, user)


def _h(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def _add(client, user, product, qty=1):
    r = client.post("/cart/items", json={"product_id": product.id, "qty": qty}, headers=_h(user))
    assert r.status_code == 200, r.text


def _checkout(client, user, address, method="cod"):
    return client.post(
        "/orders",
        json={"address_id": address.id, "payment_method": method},
        headers=_h(user),
    )


# ---- shipping rule (pure) ----
def test_shipping_fee_rule_boundaries():
    assert shipping_fee(Decimal("4999.99")) == SHIPPING_FEE_EGP
    assert shipping_fee(FREE_SHIPPING_THRESHOLD_EGP) == Decimal("0.00")
    assert shipping_fee(Decimal("10000")) == Decimal("0.00")


# ---- happy path ----
def test_successful_checkout(client, session, user, address):
    p = f.make_product(session, price_egp=Decimal("1000.00"), stock_qty=10)
    _add(client, user, p, 2)

    r = _checkout(client, user, address)
    assert r.status_code == 201
    body = r.json()
    assert len(body["orders"]) == 1
    o = body["orders"][0]
    assert o["status"] == "pending"
    assert Decimal(o["subtotal_egp"]) == Decimal("2000.00")
    assert Decimal(o["shipping_fee_egp"]) == Decimal("60.00")
    assert Decimal(o["total_egp"]) == Decimal("2060.00")
    assert o["items"][0]["qty"] == 2

    session.refresh(p)
    assert p.stock_qty == 8  # stock deducted
    assert client.get("/cart", headers=_h(user)).json()["items"] == []  # cart emptied

    history = session.scalars(
        select(OrderStatusHistory).where(OrderStatusHistory.order_id == o["id"])
    ).all()
    assert len(history) == 1
    assert history[0].from_status is None
    assert history[0].to_status == "pending"
    assert history[0].actor_type == "customer"
    assert history[0].actor_user_id == user.id


def test_address_is_snapshotted(client, session, user, address):
    _add(client, user, f.make_product(session))
    o = _checkout(client, user, address).json()["orders"][0]
    original_city = address.city
    address.city = "Changed Later"
    session.flush()
    stored = session.get(Order, o["id"])
    assert stored.shipping_address["city"] == original_city


def test_price_change_does_not_alter_old_order(client, session, user, address):
    p = f.make_product(session, price_egp=Decimal("1000.00"))
    _add(client, user, p, 1)
    order_id = _checkout(client, user, address).json()["orders"][0]["id"]

    p.price_egp = Decimal("1500.00")
    session.flush()

    item = session.scalar(select(OrderItem).where(OrderItem.order_id == order_id))
    assert item.unit_price_egp == Decimal("1000.00")


# ---- multi-seller split ----
def test_cart_with_two_sellers_creates_two_orders_in_one_group(client, session, user, address):
    p1 = f.make_product(session, price_egp=Decimal("100.00"))  # new seller each
    p2 = f.make_product(session, price_egp=Decimal("200.00"))
    assert p1.seller_id != p2.seller_id
    _add(client, user, p1)
    _add(client, user, p2)

    body = _checkout(client, user, address).json()
    assert len(body["orders"]) == 2
    assert {o["seller_id"] for o in body["orders"]} == {p1.seller_id, p2.seller_id}
    groups = {
        str(g)
        for g in session.scalars(
            select(Order.checkout_group_id).where(Order.id.in_([o["id"] for o in body["orders"]]))
        )
    }
    assert groups == {body["checkout_group_id"]}
    for o in body["orders"]:
        assert Decimal(o["total_egp"]) == Decimal(o["subtotal_egp"]) + Decimal(
            o["shipping_fee_egp"]
        )


# ---- shipping ----
def test_free_shipping_at_threshold(client, session, user, address):
    p = f.make_product(session, price_egp=Decimal("5000.00"))
    _add(client, user, p, 1)
    o = _checkout(client, user, address).json()["orders"][0]
    assert Decimal(o["shipping_fee_egp"]) == Decimal("0.00")
    assert Decimal(o["total_egp"]) == Decimal("5000.00")


# ---- payment ----
def test_cod_payment_is_pending(client, session, user, address):
    _add(client, user, f.make_product(session))
    o = _checkout(client, user, address, "cod").json()["orders"][0]
    assert o["payment_status"] == "pending"


@pytest.mark.parametrize("method", ["wallet", "card"])
def test_simulated_payment_is_paid(client, session, user, address, method):
    _add(client, user, f.make_product(session))
    o = _checkout(client, user, address, method).json()["orders"][0]
    assert o["payment_status"] == "paid"


def test_bad_payment_method_422(client, session, user, address):
    _add(client, user, f.make_product(session))
    assert _checkout(client, user, address, "bitcoin").status_code == 422


# ---- failures ----
def test_empty_cart_rejected(client, user, address):
    r = _checkout(client, user, address)
    assert r.status_code == 400
    assert r.json()["code"] == "cart_empty"


def test_other_customers_address_404(client, session, user):
    other = f.make_user(session)
    other_addr = f.make_address(session, other)
    _add(client, user, f.make_product(session))
    r = _checkout(client, user, other_addr)
    assert r.status_code == 404
    # nothing happened: cart still has the item
    assert len(client.get("/cart", headers=_h(user)).json()["items"]) == 1


def test_requires_login(client, address):
    r = client.post("/orders", json={"address_id": address.id, "payment_method": "cod"})
    assert r.status_code == 401


def test_deactivated_product_rejects_whole_order_and_rolls_back(client, session, user, address):
    ok = f.make_product(session, stock_qty=10)
    bad = f.make_product(session, stock_qty=10)
    _add(client, user, ok, 2)
    _add(client, user, bad, 1)

    bad.is_active = False
    session.flush()

    r = _checkout(client, user, address)
    assert r.status_code == 409
    assert r.json()["code"] == "checkout_unavailable"
    assert r.json()["details"][0]["product_id"] == bad.id

    session.expire_all()
    assert session.get(Product, ok.id).stock_qty == 10  # nothing deducted
    assert len(client.get("/cart", headers=_h(user)).json()["items"]) == 2  # cart intact
    count_stmt = select(func.count()).select_from(Order).where(Order.customer_id == user.id)
    assert session.scalar(count_stmt) == 0


def test_stock_drop_rejects_order(client, session, user, address):
    p = f.make_product(session, stock_qty=5)
    _add(client, user, p, 4)
    p.stock_qty = 2
    session.flush()

    r = _checkout(client, user, address)
    assert r.status_code == 409
    assert r.json()["details"][0]["reason"] == "insufficient_stock"
    assert r.json()["details"][0]["available"] == 2


def test_body_customer_id_ignored(client, session, user, address):
    victim = f.make_user(session)
    _add(client, user, f.make_product(session))
    r = client.post(
        "/orders",
        json={"address_id": address.id, "payment_method": "cod", "customer_id": victim.id},
        headers=_h(user),
    )
    assert r.status_code == 201
    order = session.get(Order, r.json()["orders"][0]["id"])
    assert order.customer_id == user.id


# ---- real concurrency (separate connections, real commits) ----
def _cart(s: Session, user_id: int) -> int:
    c = Cart(user_id=user_id)
    s.add(c)
    s.flush()
    return c.id


def _cleanup() -> None:
    """Wipe everything the committed concurrency test created (FK-safe order)."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE order_status_history, order_items, orders, cart_items, carts, "
                "product_images, reviews, returns, products, addresses, sellers, "
                "categories, brands, users RESTART IDENTITY CASCADE"
            )
        )


def test_concurrent_checkouts_on_last_item_one_wins(migrated_db):
    """Two customers race for the last unit. One succeeds, one is rejected, stock never < 0."""
    # Seed with a real commit so other connections can see the data.
    with Session(engine) as s:
        u1, u2 = f.make_user(s), f.make_user(s)
        a1, a2 = f.make_address(s, u1), f.make_address(s, u2)
        p = f.make_product(s, stock_qty=1)
        s.add_all(
            [
                CartItem(cart_id=_cart(s, u1.id), product_id=p.id, qty=1),
                CartItem(cart_id=_cart(s, u2.id), product_id=p.id, qty=1),
            ]
        )
        s.commit()
        ids = dict(u1=u1.id, u2=u2.id, a1=a1.id, a2=a2.id, p=p.id)

    results: dict[str, str] = {}
    barrier = threading.Barrier(2)

    def worker(name: str, uid: int, aid: int):
        with Session(engine) as s:
            barrier.wait()
            try:
                checkout(s, uid, aid, "cod")  # type: ignore[arg-type]
                results[name] = "ok"
            except Exception as e:  # noqa: BLE001
                results[name] = type(e).__name__

    t1 = threading.Thread(target=worker, args=("a", ids["u1"], ids["a1"]))
    t2 = threading.Thread(target=worker, args=("b", ids["u2"], ids["a2"]))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    try:
        with Session(engine) as s:
            stock = s.get(Product, ids["p"]).stock_qty
            orders = s.scalar(
                select(func.count())
                .select_from(Order)
                .where(Order.customer_id.in_([ids["u1"], ids["u2"]]))
            )
        assert sorted(results.values()) == ["ConflictError", "ok"], results
        assert stock == 0
        assert orders == 1
    finally:
        _cleanup()
