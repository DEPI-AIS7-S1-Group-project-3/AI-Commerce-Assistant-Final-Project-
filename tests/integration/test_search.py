from sqlalchemy import func, select

from ai_commerce_marketplace.database.models import Product
from ai_commerce_marketplace.nlp.arabic import build_search_text, normalize_ar
from tests import factories as f


def test_trigram_search_finds_matching_product(session):
    headphones = f.make_product(
        session, search_text=build_search_text("سماعة بلوتوث أسود", "Anker")
    )
    f.make_product(session, search_text=build_search_text("لابتوب ديل", "Dell"))

    query = normalize_ar("سماعه بلوتوث")  # العميل كتب بهاء بدل التاء المربوطة
    stmt = select(Product.id).where(func.similarity(Product.search_text, query) > 0.3)
    assert session.scalars(stmt).all() == [headphones.id]


def test_ilike_search_works_on_normalized_text(session):
    p = f.make_product(session, search_text=build_search_text("شاحن سريع", "Anker"))
    stmt = select(Product.id).where(Product.search_text.ilike(f"%{normalize_ar('شاحن')}%"))
    assert p.id in session.scalars(stmt).all()
