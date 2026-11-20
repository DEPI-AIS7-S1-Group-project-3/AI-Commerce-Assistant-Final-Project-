"""Seller inventory: list own products, change price / old price / stock / visibility.

Hiding (is_active=False) is the only way to take a product off sale: products are
referenced by orders and reviews, so they are never deleted.
"""

from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.exceptions import AppError, NotFoundError
from ai_commerce_marketplace.database.models import Brand, Category, Product, ProductImage
from ai_commerce_marketplace.nlp.arabic import normalize_ar
from ai_commerce_marketplace.schemas.seller import ProductPatchIn, SellerProductOut

LOW_STOCK = 5
Filter = Literal["all", "visible", "hidden", "low", "out"]


def _out(session: Session, p: Product, brand: Brand, category: Category) -> SellerProductOut:
    image = session.scalar(
        select(ProductImage.url)
        .where(ProductImage.product_id == p.id)
        .order_by(ProductImage.sort_order)
        .limit(1)
    )
    return SellerProductOut(
        id=p.id,
        sku=p.sku,
        title_ar=p.title_ar,
        title_en=p.title_en,
        category_slug=category.slug,
        brand=brand.name,
        price_egp=p.price_egp,
        old_price_egp=p.old_price_egp,
        stock_qty=p.stock_qty,
        is_active=p.is_active,
        rating_avg=p.rating_avg,
        rating_count=p.rating_count,
        image_url=image,
    )


def _base(seller_id: int) -> Any:  # select(Product, Brand, Category) with joins
    return (
        select(Product, Brand, Category)
        .join(Brand, Brand.id == Product.brand_id)
        .join(Category, Category.id == Product.category_id)
        .where(Product.seller_id == seller_id)
    )


def list_products(
    session: Session, seller_id: int, q: str | None = None, filter: Filter = "all"
) -> list[SellerProductOut]:
    stmt = _base(seller_id)
    if filter == "visible":
        stmt = stmt.where(Product.is_active)
    elif filter == "hidden":
        stmt = stmt.where(~Product.is_active)
    elif filter == "low":  # same definition as the dashboard (docs/seller-metrics.md)
        stmt = stmt.where(Product.is_active, Product.stock_qty <= LOW_STOCK)
    elif filter == "out":
        stmt = stmt.where(Product.stock_qty == 0)
    query = normalize_ar(q)
    if query:
        stmt = stmt.where(
            or_(
                Product.search_text.icontains(query, autoescape=True),
                Product.sku.icontains(q or "", autoescape=True),
            )
        )
    stmt = stmt.order_by(Product.is_active.desc(), Product.stock_qty, Product.id)
    return [_out(session, p, b, c) for p, b, c in session.execute(stmt).all()]


def update_product(
    session: Session, seller_id: int, product_id: int, data: ProductPatchIn
) -> SellerProductOut:
    try:
        stmt = _base(seller_id).where(Product.id == product_id).with_for_update(of=Product)
        row = session.execute(stmt).first()
        if row is None:  # also another seller's product: don't reveal it exists
            raise NotFoundError("Product not found", code="product_not_found")
        p, brand, category = row
        sent = data.model_fields_set

        price: Decimal = data.price_egp if data.price_egp is not None else p.price_egp
        old = data.old_price_egp if "old_price_egp" in sent else p.old_price_egp
        if old is not None and old <= price:
            raise AppError(
                "The old price must be higher than the price",
                code="invalid_old_price",
                details={"price_egp": str(price), "old_price_egp": str(old)},
            )

        if data.price_egp is not None:
            p.price_egp = price
        if "old_price_egp" in sent:
            p.old_price_egp = old
        if data.stock_qty is not None:
            p.stock_qty = data.stock_qty
        if data.is_active is not None:
            p.is_active = data.is_active
        session.commit()
        return _out(session, p, brand, category)
    except Exception:
        session.rollback()
        raise
