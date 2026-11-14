from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from ai_commerce_marketplace.api.main import create_app
from ai_commerce_marketplace.core.enums import ActorType, OrderStatus
from ai_commerce_marketplace.core.security import create_access_token
from ai_commerce_marketplace.database.models import Product, Review, Seller
from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.services.order_state import change_status
from tests import factories as f

S = OrderStatus


@pytest.fixture
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app, raise_server_exceptions=False)


def _h(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def _bought(session, user, product=None, delivered=True):
    order = f.make_order(session, customer_id=user.id)
    product = product or f.make_product(session)
    item = f.make_order_item(session, order=order, product=product)
    if delivered:
        for t in (S.CONFIRMED, S.SHIPPED, S.OUT_FOR_DELIVERY, S.DELIVERED):
            change_status(session, order, t, actor_type=ActorType.SYSTEM)
        order.created_at = datetime.now(UTC) - timedelta(days=5)
        order.delivered_at = datetime.now(UTC) - timedelta(days=1)
    session.commit()
    return order, item, product


def _post(client, user, item, rating=5, body="ممتاز"):
    return client.post(
        "/reviews",
        json={"order_item_id": item.id, "rating": rating, "body": body},
        headers=_h(user),
    )


# ---- writing a review ----
def test_buyer_reviews_delivered_item(client, session):
    user = f.make_user(session, full_name="منى أحمد علي")
    _, item, product = _bought(session, user)
    r = _post(client, user, item, rating=4, body="  كويسة جدًا  ")
    assert r.status_code == 201
    body = r.json()
    assert (body["rating"], body["body"], body["product_id"]) == (4, "كويسة جدًا", product.id)
    assert body["is_verified_purchase"] is True
    assert body["author_name"] == "منى"  # first name only


def test_rating_aggregates_update(client, session):
    seller = f.make_seller(session)
    p1 = f.make_product(session, seller_id=seller.id)
    p2 = f.make_product(session, seller_id=seller.id)
    a, b = f.make_user(session), f.make_user(session)
    _, i1, _ = _bought(session, a, p1)
    _, i2, _ = _bought(session, b, p1)
    _, i3, _ = _bought(session, a, p2)
    assert _post(client, a, i1, rating=5).status_code == 201
    assert _post(client, b, i2, rating=2).status_code == 201
    assert _post(client, a, i3, rating=3).status_code == 201
    session.expire_all()
    product = session.get(Product, p1.id)
    assert (product.rating_avg, product.rating_count) == (Decimal("3.50"), 2)
    assert session.get(Seller, seller.id).rating == Decimal("3.33")


def test_cannot_review_before_delivery(client, session):
    user = f.make_user(session)
    _, item, _ = _bought(session, user, delivered=False)
    r = _post(client, user, item)
    assert r.status_code == 409
    assert r.json()["code"] == "not_delivered"


def test_can_review_returned_item(client, session):
    user = f.make_user(session)
    order, item, _ = _bought(session, user)
    change_status(session, order, S.RETURN_REQUESTED, actor_type=ActorType.CUSTOMER)
    session.commit()
    assert _post(client, user, item, rating=1, body="اترجع").status_code == 201


def test_one_review_per_item(client, session):
    user = f.make_user(session)
    _, item, product = _bought(session, user)
    assert _post(client, user, item).status_code == 201
    r = _post(client, user, item, rating=1)
    assert r.status_code == 409
    assert r.json()["code"] == "review_exists"
    session.expire_all()
    assert session.get(Product, product.id).rating_count == 1


def test_cannot_review_someone_elses_item(client, session):
    owner, other = f.make_user(session), f.make_user(session)
    _, item, _ = _bought(session, owner)
    r = _post(client, other, item)
    assert r.status_code == 404
    assert r.json()["code"] == "order_item_not_found"
    assert session.scalar(select(func.count()).select_from(Review)) == 0


def test_missing_item_404(client, session):
    user = f.make_user(session)
    assert (
        client.post(
            "/reviews", json={"order_item_id": 999999, "rating": 5}, headers=_h(user)
        ).json()["code"]
        == "order_item_not_found"
    )


@pytest.mark.parametrize("rating", [0, 6, -1])
def test_rating_range_422(client, session, rating):
    user = f.make_user(session)
    _, item, _ = _bought(session, user)
    assert _post(client, user, item, rating=rating).status_code == 422


def test_body_too_long_422(client, session):
    user = f.make_user(session)
    _, item, _ = _bought(session, user)
    assert _post(client, user, item, body="x" * 2001).status_code == 422


def test_rating_without_text_allowed(client, session):
    user = f.make_user(session)
    _, item, _ = _bought(session, user)
    r = client.post("/reviews", json={"order_item_id": item.id, "rating": 3}, headers=_h(user))
    assert r.status_code == 201
    assert r.json()["body"] == ""


def test_seller_cannot_write_reviews(client, session):
    seller_user = f.make_user(session, role="seller")
    _, item, _ = _bought(session, f.make_user(session))
    assert _post(client, seller_user, item).status_code == 403


def test_review_requires_login(client):
    assert client.post("/reviews", json={"order_item_id": 1, "rating": 5}).status_code == 401


def test_customer_id_in_body_ignored(client, session):
    user, victim = f.make_user(session), f.make_user(session)
    _, item, _ = _bought(session, user)
    r = client.post(
        "/reviews",
        json={"order_item_id": item.id, "rating": 5, "customer_id": victim.id},
        headers=_h(user),
    )
    assert r.status_code == 201
    assert session.scalar(select(Review.customer_id)) == user.id


# ---- reading reviews ----
def test_product_reviews_public_newest_first_with_distribution(client, session):
    product = f.make_product(session)
    users = [f.make_user(session) for _ in range(3)]
    for u, rating in zip(users, [5, 5, 2], strict=True):
        _, item, _ = _bought(session, u, product)
        assert _post(client, u, item, rating=rating, body=f"تقييم {rating}").status_code == 201

    r = client.get(f"/products/{product.id}/reviews")  # no login
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == body["rating_count"] == 3
    assert body["rating_avg"] == "4.00"
    assert body["distribution"] == {"1": 0, "2": 1, "3": 0, "4": 0, "5": 2}
    assert [rv["rating"] for rv in body["reviews"]] == [2, 5, 5]  # newest first
    assert "customer_id" not in body["reviews"][0]


def test_product_reviews_pagination(client, session):
    product = f.make_product(session)
    for _ in range(3):
        u = f.make_user(session)
        _, item, _ = _bought(session, u, product)
        _post(client, u, item)
    r = client.get(f"/products/{product.id}/reviews?limit=2&offset=2").json()
    assert (r["total"], len(r["reviews"])) == (3, 1)
    assert client.get(f"/products/{product.id}/reviews?limit=0").status_code == 422


def test_product_without_reviews(client, session):
    product = f.make_product(session)
    body = client.get(f"/products/{product.id}/reviews").json()
    assert (body["total"], body["rating_avg"], body["reviews"]) == (0, None, [])


def test_unknown_product_404(client):
    r = client.get("/products/999999/reviews")
    assert r.status_code == 404
    assert r.json()["code"] == "product_not_found"


def test_reviewable_and_mine(client, session):
    user = f.make_user(session)
    _, done, _ = _bought(session, user)
    _, todo, _ = _bought(session, user)
    _bought(session, user, delivered=False)  # not delivered: not reviewable
    _bought(session, f.make_user(session))  # someone else's
    _post(client, user, done)

    reviewable = client.get("/reviews/reviewable", headers=_h(user)).json()
    assert [x["order_item_id"] for x in reviewable] == [todo.id]
    mine = client.get("/reviews/mine", headers=_h(user)).json()
    assert [x["order_item_id"] for x in mine] == [done.id]
