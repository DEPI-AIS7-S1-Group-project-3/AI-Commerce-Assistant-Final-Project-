from decimal import Decimal

import pytest

from ai_commerce_marketplace.core.exceptions import NotFoundError
from ai_commerce_marketplace.database.models import ProductImage
from ai_commerce_marketplace.services.catalog_details import get_product
from tests import factories as f


# ---- get_product ----
def test_get_product_returns_full_detail(session):
    brand = f.make_brand(session, name="Samsung", name_ar="سامسونج")
    cat = f.make_category(session, slug="mobiles-x")
    p = f.make_product(
        session,
        brand_id=brand.id,
        category_id=cat.id,
        price_egp=Decimal("9999.00"),
        old_price_egp=Decimal("10999.00"),
        warranty_months=12,
        specs={"ram_gb": 8, "network": "5g"},
    )
    session.add_all(
        [
            ProductImage(product_id=p.id, url="b.jpg", sort_order=2),
            ProductImage(product_id=p.id, url="a.jpg", sort_order=1),
        ]
    )
    session.flush()

    d = get_product(session, p.id)

    assert d.id == p.id
    assert d.brand == "سامسونج"
    assert d.category_slug == "mobiles-x"
    assert d.price_egp == Decimal("9999.00")
    assert d.old_price_egp == Decimal("10999.00")
    assert d.warranty_months == 12
    assert d.specs == {"ram_gb": 8, "network": "5g"}
    assert d.image_urls == ["a.jpg", "b.jpg"]
    assert d.in_stock is True


def test_brand_falls_back_to_english_name(session):
    brand = f.make_brand(session, name="Anker", name_ar=None)
    p = f.make_product(session, brand_id=brand.id)
    assert get_product(session, p.id).brand == "Anker"


def test_inactive_product_is_returned_but_not_in_stock(session):
    p = f.make_product(session, is_active=False, stock_qty=5)
    d = get_product(session, p.id)
    assert d.in_stock is False
    assert d.stock_qty == 5


def test_zero_stock_is_not_in_stock(session):
    p = f.make_product(session, stock_qty=0)
    assert get_product(session, p.id).in_stock is False


def test_missing_product_raises_not_found(session):
    with pytest.raises(NotFoundError) as e:
        get_product(session, 999_999)
    assert e.value.code == "product_not_found"
