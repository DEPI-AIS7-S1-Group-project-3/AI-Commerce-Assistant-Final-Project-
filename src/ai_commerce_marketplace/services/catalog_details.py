"""Read-only product detail and comparison for the Shopping Agent.

Decisions (agreed with the team):
- Inactive or out-of-stock products are still returned, with in_stock=False,
  so the agent can say "not available now".
- Brand shown is the Arabic name, falling back to the English name.
- Compare: 2 to 4 distinct ids, duplicates removed, unknown ids reported in
  missing_ids, fewer than 2 found is an error, mixed categories are rejected.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.agents.shopping.schemas import ProductDetail
from ai_commerce_marketplace.core.enums import SpecKind
from ai_commerce_marketplace.core.exceptions import AppError, NotFoundError
from ai_commerce_marketplace.database.models import Brand, Category, Product, ProductImage
from ai_commerce_marketplace.schemas.specs import SPEC_MODELS

MIN_COMPARE = 2
MAX_COMPARE = 4

Row = tuple[Product, Brand, Category]


def _load(session: Session, ids: list[int]) -> dict[int, Row]:
    """Products with their brand and category, keyed by product id."""
    stmt = (
        select(Product, Brand, Category)
        .join(Brand, Brand.id == Product.brand_id)
        .join(Category, Category.id == Product.category_id)
        .where(Product.id.in_(ids))
    )
    return {p.id: (p, b, c) for p, b, c in session.execute(stmt)}


def _image_urls(session: Session, product_id: int) -> list[str]:
    stmt = (
        select(ProductImage.url)
        .where(ProductImage.product_id == product_id)
        .order_by(ProductImage.sort_order)
    )
    return list(session.scalars(stmt))


def _to_detail(session: Session, p: Product, brand: Brand, category: Category) -> ProductDetail:
    return ProductDetail(
        id=p.id,
        title_ar=p.title_ar,
        brand=brand.name_ar or brand.name,
        category_slug=category.slug,
        price_egp=p.price_egp,
        old_price_egp=p.old_price_egp,
        rating_avg=p.rating_avg,
        rating_count=p.rating_count,
        in_stock=p.is_active and p.stock_qty > 0,
        description_ar=p.description_ar,
        warranty_months=p.warranty_months,
        is_returnable=p.is_returnable,
        stock_qty=p.stock_qty,
        specs=p.specs,
        image_urls=_image_urls(session, p.id),
    )


def _spec_keys(category: Category) -> list[str]:
    """Official spec fields for the category's spec_kind (see schemas/specs.py)."""
    if category.spec_kind is None:
        return []
    return list(SPEC_MODELS[SpecKind(category.spec_kind)].model_fields)


def get_product(session: Session, product_id: int) -> ProductDetail:
    """Full detail for one product. Raises NotFoundError if the id does not exist."""
    found = _load(session, [product_id])
    if product_id not in found:
        raise NotFoundError("Product not found", code="product_not_found")
    return _to_detail(session, *found[product_id])


def compare_products(session: Session, product_ids: list[int]) -> dict[str, Any]:
    """Compare 2 to 4 products of the same kind, in the order they were asked for."""
    ids = list(dict.fromkeys(product_ids))  # remove duplicates, keep order
    if not MIN_COMPARE <= len(ids) <= MAX_COMPARE:
        raise AppError(
            f"Compare needs {MIN_COMPARE} to {MAX_COMPARE} different products",
            code="invalid_ids_count",
        )

    found = _load(session, ids)
    missing = [i for i in ids if i not in found]
    rows = [found[i] for i in ids if i in found]
    if len(rows) < MIN_COMPARE:
        raise AppError(
            f"Not enough products to compare. Missing ids: {missing}",
            code="not_enough_products",
            details={"missing_ids": missing},
        )

    if len({c.spec_kind for _, _, c in rows}) > 1:
        raise AppError(
            "Products are from different categories and cannot be compared",
            code="mixed_categories",
        )

    return {
        "products": [_to_detail(session, *row) for row in rows],
        "spec_keys": _spec_keys(rows[0][2]),
        "missing_ids": missing,
    }
