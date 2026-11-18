import pytest

from ai_commerce_marketplace.core.exceptions import AppError
from ai_commerce_marketplace.services import catalog
from tests import factories as f


def mine(rows, products):
    """Ids of this test's products, in the order the service returned them."""
    wanted = {p.id for p in products}
    return [r.id for r in rows if r.id in wanted]


def test_min_filter_keeps_products_at_or_above(session):
    a = f.make_product(session, specs={"ram_gb": 4})
    b = f.make_product(session, specs={"ram_gb": 8})
    c = f.make_product(session, specs={"ram_gb": 12})

    rows = catalog.list_products(session, specs={"ram_gb_min": 8}, limit=100)

    assert set(mine(rows, [a, b, c])) == {b.id, c.id}


def test_exact_filter_on_text_spec(session):
    a = f.make_product(session, specs={"network": "4g"})
    b = f.make_product(session, specs={"network": "5g"})

    rows = catalog.list_products(session, specs={"network": "5g"}, limit=100)

    assert mine(rows, [a, b]) == [b.id]


def test_exact_filter_on_boolean_spec(session):
    a = f.make_product(session, specs={"wireless": False})
    b = f.make_product(session, specs={"wireless": True})

    rows = catalog.list_products(session, specs={"wireless": True}, limit=100)

    assert mine(rows, [a, b]) == [b.id]


def test_spec_filters_combine(session):
    a = f.make_product(session, specs={"ram_gb": 8, "network": "4g"})
    b = f.make_product(session, specs={"ram_gb": 8, "network": "5g"})
    c = f.make_product(session, specs={"ram_gb": 4, "network": "5g"})

    rows = catalog.list_products(session, specs={"ram_gb_min": 8, "network": "5g"}, limit=100)

    assert mine(rows, [a, b, c]) == [b.id]


def test_unknown_spec_key_is_rejected(session):
    with pytest.raises(AppError) as err:
        catalog.list_products(session, specs={"colour": "red"})
    assert err.value.code == "invalid_spec_filter"


def test_wrong_value_type_is_rejected(session):
    with pytest.raises(AppError) as err:
        catalog.list_products(session, specs={"ram_gb_min": "lots"})
    assert err.value.code == "invalid_spec_filter"


def test_sort_spec_orders_high_to_low_and_missing_last(session):
    low = f.make_product(session, specs={"battery_mah": 3000})
    high = f.make_product(session, specs={"battery_mah": 5000})
    mid = f.make_product(session, specs={"battery_mah": 4000})
    none = f.make_product(session, specs={})

    rows = catalog.list_products(session, sort_spec="battery_mah", limit=100)

    assert mine(rows, [low, high, mid, none]) == [high.id, mid.id, low.id, none.id]


def test_unknown_sort_spec_is_rejected(session):
    with pytest.raises(AppError) as err:
        catalog.list_products(session, sort_spec="colour")
    assert err.value.code == "invalid_spec_filter"


def test_without_spec_arguments_nothing_changes(session):
    p = f.make_product(session, specs={"ram_gb": 4})

    rows = catalog.list_products(session, limit=100)

    assert p.id in {r.id for r in rows}
