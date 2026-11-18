from decimal import Decimal

from ai_commerce_marketplace.agents.shopping.tools import ToolContext, call_tool
from tests import factories as f


def search(session, **args):
    return call_tool(ToolContext(session=session), "search_products", args)


def test_returns_product_cards(session):
    brand = f.make_brand(session, name="Samsung", name_ar="سامسونج")
    cat = f.make_category(session, slug="srch-cards")
    p = f.make_product(session, brand_id=brand.id, category_id=cat.id, price_egp=Decimal("9999.00"))

    r = search(session, category="srch-cards")

    assert r["ok"] is True
    assert r["empty"] is False
    assert r["count"] == 1
    card = r["products"][0]
    assert card["id"] == p.id
    assert card["brand"] == "سامسونج"
    assert card["category_slug"] == "srch-cards"
    assert card["price_egp"] == "9999.00"
    assert card["in_stock"] is True


def test_out_of_stock_hidden_by_default_and_shown_when_asked(session):
    cat = f.make_category(session, slug="srch-stock")
    on = f.make_product(session, category_id=cat.id)
    off = f.make_product(session, category_id=cat.id, stock_qty=0)

    default = search(session, category="srch-stock")
    everything = search(session, category="srch-stock", in_stock_only=False)

    assert [c["id"] for c in default["products"]] == [on.id]
    by_id = {c["id"]: c for c in everything["products"]}
    assert set(by_id) == {on.id, off.id}
    assert by_id[off.id]["in_stock"] is False


def test_inactive_products_never_appear(session):
    cat = f.make_category(session, slug="srch-inactive")
    f.make_product(session, category_id=cat.id, is_active=False)

    r = search(session, category="srch-inactive", in_stock_only=False)

    assert r["ok"] is True
    assert r["empty"] is True


def test_price_range_filter(session):
    cat = f.make_category(session, slug="srch-price")
    cheap = f.make_product(session, category_id=cat.id, price_egp=Decimal("500"))
    mid = f.make_product(session, category_id=cat.id, price_egp=Decimal("5000"))
    f.make_product(session, category_id=cat.id, price_egp=Decimal("50000"))

    r = search(session, category="srch-price", min_price=100, max_price="10000", sort="price_asc")

    assert [c["id"] for c in r["products"]] == [cheap.id, mid.id]


def test_spec_filters_and_sort_through_the_tool(session):
    cat = f.make_category(session, slug="srch-specs")
    f.make_product(session, category_id=cat.id, specs={"network": "4g", "battery_mah": 6000})
    low = f.make_product(session, category_id=cat.id, specs={"network": "5g", "battery_mah": 4000})
    high = f.make_product(session, category_id=cat.id, specs={"network": "5g", "battery_mah": 5000})

    r = search(session, category="srch-specs", specs={"network": "5g"}, sort_spec="battery_mah")

    assert [c["id"] for c in r["products"]] == [high.id, low.id]


def test_no_match_is_reported_as_empty_not_error(session):
    r = search(session, category="no-such-category")

    assert r["ok"] is True
    assert r["empty"] is True
    assert r["products"] == []


def test_limit_is_applied_and_validated(session):
    cat = f.make_category(session, slug="srch-limit")
    for _ in range(3):
        f.make_product(session, category_id=cat.id)

    assert search(session, category="srch-limit", limit=2)["count"] == 2
    assert search(session, category="srch-limit", limit=0)["error"] == "invalid_limit"


def test_bad_inputs_return_errors_instead_of_raising(session):
    assert search(session, sort="cheapest")["error"] == "invalid_sort"
    assert search(session, specs={"colour": "red"})["error"] == "invalid_spec_filter"
    assert search(session, specs="5g")["error"] == "invalid_specs"
    assert search(session, min_price="cheap")["error"] == "invalid_price"
    assert search(session, in_stock_only="yes")["error"] == "invalid_in_stock_only"


def test_customer_id_argument_is_rejected(session):
    r = search(session, customer_id=1)

    assert r["ok"] is False
    assert r["error"] == "forbidden_argument"


def test_categories_brands_list_returns_slugs(session):
    f.make_category(session, slug="list-phones", name_ar="موبايلات", name_en="Phones")
    f.make_brand(session, slug="list-samsung", name="Samsung", name_ar="سامسونج")

    r = call_tool(ToolContext(session=session), "categories_brands_list", {})

    assert r["ok"] is True
    assert r["empty"] is False
    cats = {c["slug"]: c for c in r["categories"]}
    brands = {b["slug"]: b for b in r["brands"]}
    assert cats["list-phones"] == {
        "slug": "list-phones",
        "name_ar": "موبايلات",
        "name_en": "Phones",
        "spec_kind": "mobile",
    }
    assert brands["list-samsung"] == {
        "slug": "list-samsung",
        "name": "Samsung",
        "name_ar": "سامسونج",
    }


def test_categories_brands_list_hides_internal_ids(session):
    f.make_category(session, slug="list-ids")

    r = call_tool(ToolContext(session=session), "categories_brands_list", {})

    assert all("id" not in c for c in r["categories"])
    assert all("id" not in b for b in r["brands"])


def test_categories_brands_list_rejects_customer_id(session):
    r = call_tool(ToolContext(session=session), "categories_brands_list", {"customer_id": 1})

    assert r["ok"] is False
    assert r["error"] == "forbidden_argument"
