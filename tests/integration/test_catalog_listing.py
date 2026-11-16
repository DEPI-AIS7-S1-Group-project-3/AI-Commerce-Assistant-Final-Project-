from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from ai_commerce_marketplace.api.main import create_app
from ai_commerce_marketplace.database.models import ProductImage
from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.nlp.arabic import build_search_text
from tests import factories as f

T0 = datetime(2026, 10, 1, tzinfo=UTC)


@pytest.fixture
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app, raise_server_exceptions=False)


def ids(r, mine):
    """Ids from a /products response, keeping only products this test created, in order."""
    assert r.status_code == 200, r.text
    wanted = {p.id for p in mine}
    return [p["id"] for p in r.json() if p["id"] in wanted]


# ---- visibility ----
def test_inactive_hidden_out_of_stock_shown(session, client):
    on = f.make_product(session)
    hidden = f.make_product(session, is_active=False)
    empty = f.make_product(session, stock_qty=0)

    got = ids(client.get("/products?limit=100"), [on, hidden, empty])

    assert set(got) == {on.id, empty.id}


def test_in_stock_filter(session, client):
    on = f.make_product(session)
    empty = f.make_product(session, stock_qty=0)
    assert ids(client.get("/products?in_stock=true&limit=100"), [on, empty]) == [on.id]


# ---- filters ----
def test_category_filter_and_parent_includes_children(session, client):
    parent = f.make_category(session, spec_kind=None)
    phones = f.make_category(session, parent_id=parent.id, spec_kind="mobile")
    audio = f.make_category(session, parent_id=parent.id, spec_kind="audio")
    a = f.make_product(session, category_id=phones.id)
    b = f.make_product(session, category_id=audio.id)

    assert ids(client.get(f"/products?category={phones.slug}"), [a, b]) == [a.id]
    assert set(ids(client.get(f"/products?category={parent.slug}"), [a, b])) == {a.id, b.id}


def test_brand_filter(session, client):
    sam = f.make_brand(session)
    a = f.make_product(session, brand_id=sam.id)
    b = f.make_product(session)
    assert ids(client.get(f"/products?brand={sam.slug}"), [a, b]) == [a.id]


def test_price_range(session, client):
    cheap = f.make_product(session, price_egp=Decimal("1000.00"))
    mid = f.make_product(session, price_egp=Decimal("5000.00"))
    pricey = f.make_product(session, price_egp=Decimal("20000.00"))
    r = client.get("/products?min_price=2000&max_price=10000&limit=100")
    assert ids(r, [cheap, mid, pricey]) == [mid.id]


# ---- search ----
def test_search_arabic_normalized(session, client):
    hp = f.make_product(session, search_text=build_search_text("سماعة بلوتوث", "Anker"))
    other = f.make_product(session, search_text=build_search_text("لابتوب ديل", "Dell"))
    # customer typed ه instead of ة
    assert ids(client.get("/products?q=سماعه"), [hp, other]) == [hp.id]


def test_search_tolerates_small_typo(session, client):
    s = f.make_product(session, search_text=build_search_text("هاتف", "Samsung Galaxy"))
    other = f.make_product(session, search_text=build_search_text("لابتوب", "Lenovo"))
    assert ids(client.get("/products?q=samsng"), [s, other]) == [s.id]


def test_search_with_only_symbols_is_ignored(session, client):
    p = f.make_product(session, search_text=build_search_text("شاحن"))
    # normalize_ar strips symbols, so "%" becomes an empty search, not a wildcard
    assert ids(client.get("/products?q=%25&limit=100"), [p]) == [p.id]


def test_search_no_match_is_empty(session, client):
    p = f.make_product(session, search_text=build_search_text("شاحن"))
    assert ids(client.get("/products?q=xyzxyzqq"), [p]) == []


# ---- sort + paging ----
def _product(session, price, rating, days, **kw):
    return f.make_product(
        session,
        price_egp=Decimal(price),
        rating_avg=None if rating is None else Decimal(rating),
        created_at=T0 + timedelta(days=days),
        **kw,
    )


def test_sorts(session, client):
    a = _product(session, "300.00", "4.10", 0)
    b = _product(session, "100.00", "4.90", 2)
    c = _product(session, "200.00", None, 1)
    mine = [a, b, c]

    assert ids(client.get("/products?sort=price_asc&limit=100"), mine) == [b.id, c.id, a.id]
    assert ids(client.get("/products?sort=price_desc&limit=100"), mine) == [a.id, c.id, b.id]
    assert ids(client.get("/products?sort=rating&limit=100"), mine) == [b.id, a.id, c.id]
    assert ids(client.get("/products?sort=newest&limit=100"), mine) == [b.id, c.id, a.id]


def test_limit_and_offset(session, client):
    brand = f.make_brand(session)
    made = [_product(session, f"{100 + i}.00", None, 0, brand_id=brand.id) for i in range(5)]
    base = f"/products?brand={brand.slug}&sort=price_asc"
    assert ids(client.get(f"{base}&limit=2"), made) == [made[0].id, made[1].id]
    assert ids(client.get(f"{base}&limit=2&offset=2"), made) == [made[2].id, made[3].id]


BAD_QUERIES = ["sort=cheapest", "limit=0", "limit=101", "offset=-1", "min_price=-5"]


@pytest.mark.parametrize("query", BAD_QUERIES)
def test_bad_params_are_422(client, query):
    r = client.get(f"/products?{query}")
    assert r.status_code == 422
    assert r.json()["code"] == "validation_error"


def test_list_items_have_full_shape_with_images(session, client):
    brand = f.make_brand(session)
    p = f.make_product(session, brand_id=brand.id)
    session.add(ProductImage(product_id=p.id, url="/static/x.svg", sort_order=1))
    session.flush()
    item = next(i for i in client.get(f"/products?brand={brand.slug}").json() if i["id"] == p.id)
    assert item["images"] == [{"url": "/static/x.svg", "alt_ar": None}]
    assert set(item["brand"]) == {"id", "slug", "name", "name_ar"}
    assert isinstance(item["price_egp"], str)


# ---- categories + brands ----
def test_categories_are_leaves_in_order(session, client):
    parent = f.make_category(session, spec_kind=None, sort_order=1)
    second = f.make_category(session, parent_id=parent.id, sort_order=3)
    first = f.make_category(session, parent_id=parent.id, sort_order=2)

    r = client.get("/categories")

    assert r.status_code == 200
    slugs = [c["slug"] for c in r.json()]
    assert parent.slug not in slugs
    assert slugs.index(first.slug) < slugs.index(second.slug)


def test_brands_sorted_by_name(session, client):
    z = f.make_brand(session, name="Zzz Brand Test")
    a = f.make_brand(session, name="Aaa Brand Test")
    names = [b["name"] for b in client.get("/brands").json()]
    assert names.index(a.name) < names.index(z.name)
    assert set(client.get("/brands").json()[0]) == {"id", "slug", "name", "name_ar"}
