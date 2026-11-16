from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from ai_commerce_marketplace.api.main import create_app
from ai_commerce_marketplace.database.models import ProductImage
from ai_commerce_marketplace.database.session import get_session
from tests import factories as f


@pytest.fixture
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app, raise_server_exceptions=False)


def test_get_product_full_shape(session, client):
    brand = f.make_brand(session, name="Samsung", name_ar="سامسونج")
    cat = f.make_category(session, spec_kind="mobile")
    p = f.make_product(
        session,
        brand_id=brand.id,
        category_id=cat.id,
        price_egp=Decimal("9999.00"),
        old_price_egp=Decimal("10999.00"),
    )
    session.add_all(
        [
            ProductImage(product_id=p.id, url="/static/b.svg", sort_order=2),
            ProductImage(product_id=p.id, url="/static/a.svg", alt_ar="صورة", sort_order=1),
        ]
    )
    session.flush()

    r = client.get(f"/products/{p.id}")  # no Authorization header: public

    assert r.status_code == 200
    body = r.json()
    assert body["id"] == p.id
    assert body["price_egp"] == "9999.00"  # exact string, like /cart
    assert body["old_price_egp"] == "10999.00"
    assert body["is_active"] is True
    assert body["brand"] == {
        "id": brand.id,
        "slug": brand.slug,
        "name": "Samsung",
        "name_ar": "سامسونج",
    }
    assert body["category"]["spec_kind"] == "mobile"
    assert set(body["seller"]) == {"id", "store_name", "rating"}
    assert body["images"] == [
        {"url": "/static/a.svg", "alt_ar": "صورة"},
        {"url": "/static/b.svg", "alt_ar": None},
    ]


def test_inactive_product_is_returned(session, client):
    p = f.make_product(session, is_active=False)
    r = client.get(f"/products/{p.id}")
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_missing_product_is_404(client):
    r = client.get("/products/999999")
    assert r.status_code == 404
    assert r.json()["code"] == "product_not_found"


def test_non_numeric_id_is_422(client):
    r = client.get("/products/abc")
    assert r.status_code == 422
    assert r.json()["code"] == "validation_error"


def test_product_images_are_served(client):
    r = client.get("/static/products/MOB-SAM-D140-4-128-1.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")


def test_missing_static_file_uses_unified_404(client):
    r = client.get("/static/products/nope.svg")
    assert r.status_code == 404
    assert r.json()["code"] == "not_found"
