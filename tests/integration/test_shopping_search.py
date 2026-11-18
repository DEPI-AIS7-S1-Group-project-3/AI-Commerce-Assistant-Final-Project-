from ai_commerce_marketplace.services.catalog_search import list_categories_brands
from tests import factories as f


def test_lists_categories_and_brands_with_slugs(session):
    f.make_category(session, slug="test-mobiles", name_ar="موبايلات", name_en="Mobiles")
    f.make_brand(session, slug="test-samsung", name="TestSamsung", name_ar="سامسونج")

    result = list_categories_brands(session)

    categories = {c["slug"]: c for c in result["categories"]}
    brands = {b["slug"]: b for b in result["brands"]}
    assert categories["test-mobiles"]["name_ar"] == "موبايلات"
    assert set(categories["test-mobiles"]) == {
        "id",
        "slug",
        "name_ar",
        "name_en",
        "parent_id",
        "spec_kind",
    }
    assert brands["test-samsung"]["name"] == "TestSamsung"
