from decimal import Decimal

import pytest

from ai_commerce_marketplace.core.exceptions import AppError, NotFoundError
from ai_commerce_marketplace.database.models import ProductImage
from ai_commerce_marketplace.services.catalog_details import compare_products, get_product
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


# ---- compare_products ----
MOBILE_KEYS = [
    "ram_gb",
    "storage_gb",
    "screen_inch",
    "battery_mah",
    "camera_mp",
    "os",
    "network",
    "color_ar",
]


@pytest.fixture
def mobiles(session):
    return f.make_category(session, spec_kind="mobile")


def test_compare_returns_products_in_requested_order(session, mobiles):
    a = f.make_product(session, category_id=mobiles.id)
    b = f.make_product(session, category_id=mobiles.id)

    r = compare_products(session, [b.id, a.id])

    assert [p.id for p in r["products"]] == [b.id, a.id]
    assert r["spec_keys"] == MOBILE_KEYS
    assert r["missing_ids"] == []


def test_compare_removes_duplicate_ids(session, mobiles):
    a = f.make_product(session, category_id=mobiles.id)
    b = f.make_product(session, category_id=mobiles.id)

    r = compare_products(session, [a.id, a.id, b.id])

    assert [p.id for p in r["products"]] == [a.id, b.id]


def test_compare_reports_missing_ids(session, mobiles):
    a = f.make_product(session, category_id=mobiles.id)
    b = f.make_product(session, category_id=mobiles.id)

    r = compare_products(session, [a.id, 999_999, b.id])

    assert [p.id for p in r["products"]] == [a.id, b.id]
    assert r["missing_ids"] == [999_999]


def test_compare_includes_unavailable_products(session, mobiles):
    a = f.make_product(session, category_id=mobiles.id)
    b = f.make_product(session, category_id=mobiles.id, is_active=False)

    r = compare_products(session, [a.id, b.id])

    assert [p.in_stock for p in r["products"]] == [True, False]


def test_compare_fails_when_fewer_than_two_found(session, mobiles):
    a = f.make_product(session, category_id=mobiles.id)
    with pytest.raises(AppError) as e:
        compare_products(session, [a.id, 999_999])
    assert e.value.code == "not_enough_products"
    assert e.value.details == {"missing_ids": [999_999]}


@pytest.mark.parametrize("count", [1, 5])
def test_compare_rejects_wrong_number_of_ids(session, count):
    with pytest.raises(AppError) as e:
        compare_products(session, list(range(1, count + 1)))
    assert e.value.code == "invalid_ids_count"


def test_compare_rejects_one_id_repeated(session, mobiles):
    a = f.make_product(session, category_id=mobiles.id)
    with pytest.raises(AppError) as e:
        compare_products(session, [a.id, a.id])
    assert e.value.code == "invalid_ids_count"


def test_compare_rejects_mixed_categories(session, mobiles):
    audio = f.make_category(session, spec_kind="audio")
    a = f.make_product(session, category_id=mobiles.id)
    b = f.make_product(session, category_id=audio.id)
    with pytest.raises(AppError) as e:
        compare_products(session, [a.id, b.id])
    assert e.value.code == "mixed_categories"
