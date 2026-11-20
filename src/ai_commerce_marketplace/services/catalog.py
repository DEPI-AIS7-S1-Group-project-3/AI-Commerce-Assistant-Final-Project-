"""Public (website) catalog reads. No login needed.

Rules:
- Product page (get_product): inactive products are still returned with is_active=False,
  so old links and cart items open a "not available now" page instead of a 404.
- Listing (list_products): inactive products are never shown. Out-of-stock products are
  shown (as out of stock) unless in_stock=True.
- Search: normalized substring match OR trigram word similarity (catches small typos).
"""

from collections import defaultdict
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from ai_commerce_marketplace.core.exceptions import AppError, NotFoundError
from ai_commerce_marketplace.database.models import (
    Brand,
    Category,
    Product,
    ProductImage,
    Seller,
)
from ai_commerce_marketplace.nlp.arabic import normalize_ar
from ai_commerce_marketplace.schemas.catalog import (
    BrandOut,
    CategoryOut,
    ProductImageOut,
    ProductOut,
    SellerSummaryOut,
)

ProductSort = Literal["newest", "price_asc", "price_desc", "rating"]

FUZZY_THRESHOLD = 0.5  # pg_trgm word_similarity; 1.0 = exact word match
# Spec filters the agent may use (keys match schemas/specs.py).
# "<key>_min" means "at least"; the others are exact matches.
SPEC_MIN_KEYS = frozenset(
    {"ram_gb", "storage_gb", "battery_mah", "battery_hours", "camera_mp", "screen_inch"}
)
SPEC_TEXT_KEYS = frozenset({"network", "os", "storage_type", "type", "connector"})
SPEC_BOOL_KEYS = frozenset({"wireless", "noise_cancelling"})


def _spec(key: str) -> Any:
    """products.specs[key] as a JSONB element (typed Any so .as_float() type-checks)."""
    column: Any = Product.specs
    return column[key]


def _bad_spec(message: str) -> AppError:
    return AppError(message, code="invalid_spec_filter")


def _spec_conditions(specs: dict[str, Any]) -> list[Any]:
    conditions: list[Any] = []
    for key, value in specs.items():
        if key.endswith("_min") and key[:-4] in SPEC_MIN_KEYS:
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise _bad_spec(f"{key} must be a number")
            conditions.append(_spec(key[:-4]).as_float() >= value)
        elif key in SPEC_TEXT_KEYS:
            if not isinstance(value, str):
                raise _bad_spec(f"{key} must be text")
            conditions.append(_spec(key).as_string() == value)
        elif key in SPEC_BOOL_KEYS:
            if not isinstance(value, bool):
                raise _bad_spec(f"{key} must be true or false")
            conditions.append(_spec(key).as_boolean() == value)
        else:
            raise _bad_spec(f"Unknown spec filter: {key}")
    return conditions


def _base() -> Any:  # select(Product, Brand, Category, Seller) with joins
    return (
        select(Product, Brand, Category, Seller)
        .join(Brand, Brand.id == Product.brand_id)
        .join(Category, Category.id == Product.category_id)
        .join(Seller, Seller.id == Product.seller_id)
    )


def _images(session: Session, product_ids: list[int]) -> dict[int, list[ProductImageOut]]:
    """All images for these products in one query, in sort_order."""
    out: dict[int, list[ProductImageOut]] = defaultdict(list)
    if not product_ids:
        return out
    stmt = (
        select(ProductImage)
        .where(ProductImage.product_id.in_(product_ids))
        .order_by(ProductImage.product_id, ProductImage.sort_order)
    )
    for img in session.scalars(stmt):
        out[img.product_id].append(ProductImageOut.model_validate(img))
    return out


def _to_out(
    p: Product, brand: Brand, category: Category, seller: Seller, images: list[ProductImageOut]
) -> ProductOut:
    return ProductOut(
        id=p.id,
        sku=p.sku,
        title_ar=p.title_ar,
        title_en=p.title_en,
        description_ar=p.description_ar,
        price_egp=p.price_egp,
        old_price_egp=p.old_price_egp,
        stock_qty=p.stock_qty,
        warranty_months=p.warranty_months,
        is_returnable=p.is_returnable,
        is_active=p.is_active,
        specs=p.specs,
        rating_avg=p.rating_avg,
        rating_count=p.rating_count,
        created_at=p.created_at,
        images=images,
        seller=SellerSummaryOut.model_validate(seller),
        brand=BrandOut.model_validate(brand),
        category=CategoryOut.model_validate(category),
    )


def get_product(session: Session, product_id: int) -> ProductOut:
    row = session.execute(_base().where(Product.id == product_id)).first()
    if row is None:
        raise NotFoundError("Product not found", code="product_not_found")
    p, brand, category, seller = row
    return _to_out(p, brand, category, seller, _images(session, [p.id])[p.id])


def list_products(
    session: Session,
    *,
    q: str | None = None,
    category: str | None = None,
    brand: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    in_stock: bool = False,
    sort: ProductSort = "newest",
    limit: int = 50,
    offset: int = 0,
    specs: dict[str, Any] | None = None,
    sort_spec: str | None = None,
) -> list[ProductOut]:
    stmt = _base().where(Product.is_active)

    if category:
        # A parent slug (e.g. "electronics") also matches its child categories.
        parent = aliased(Category)
        child_of = exists().where(parent.id == Category.parent_id, parent.slug == category)
        stmt = stmt.where(or_(Category.slug == category, child_of))
    if brand:
        stmt = stmt.where(Brand.slug == brand)
    if min_price is not None:
        stmt = stmt.where(Product.price_egp >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price_egp <= max_price)
    if in_stock:
        stmt = stmt.where(Product.stock_qty > 0)
    if specs:
        stmt = stmt.where(*_spec_conditions(specs))
    query = normalize_ar(q)
    if query:
        stmt = stmt.where(
            or_(
                Product.search_text.icontains(query, autoescape=True),
                func.word_similarity(query, Product.search_text) > FUZZY_THRESHOLD,
            )
        )

    order: dict[str, Any] = {
        "newest": (Product.created_at.desc(), Product.id.desc()),
        "price_asc": (Product.price_egp.asc(), Product.id.asc()),
        "price_desc": (Product.price_egp.desc(), Product.id.asc()),
        "rating": (
            Product.rating_avg.desc().nulls_last(),
            Product.rating_count.desc(),
            Product.id.asc(),
        ),
    }
    if sort_spec is not None:
        if sort_spec not in SPEC_MIN_KEYS:
            raise _bad_spec(f"Cannot sort by {sort_spec}")
        ordering: Any = (_spec(sort_spec).as_float().desc().nulls_last(), Product.id.asc())
    else:
        ordering = order[sort]
    stmt = stmt.order_by(*ordering).limit(limit).offset(offset)

    rows = session.execute(stmt).all()
    images = _images(session, [p.id for p, *_ in rows])
    return [_to_out(p, b, c, s, images[p.id]) for p, b, c, s in rows]


def list_categories(session: Session) -> list[CategoryOut]:
    """Leaf categories only (the ones products belong to), in their display order."""
    child = aliased(Category)
    has_children = exists().where(child.parent_id == Category.id)
    stmt = select(Category).where(~has_children).order_by(Category.sort_order, Category.id)
    return [CategoryOut.model_validate(c) for c in session.scalars(stmt)]


def list_brands(session: Session) -> list[BrandOut]:
    stmt = select(Brand).order_by(Brand.name)
    return [BrandOut.model_validate(b) for b in session.scalars(stmt)]
