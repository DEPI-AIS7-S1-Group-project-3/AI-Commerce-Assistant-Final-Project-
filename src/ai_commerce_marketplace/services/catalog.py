"""Public (website) catalog reads. No login needed.

Inactive products are still returned with is_active=False so old links and cart
items open a "not available now" page instead of a 404.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.exceptions import NotFoundError
from ai_commerce_marketplace.database.models import (
    Brand,
    Category,
    Product,
    ProductImage,
    Seller,
)
from ai_commerce_marketplace.schemas.catalog import (
    BrandOut,
    CategoryOut,
    ProductImageOut,
    ProductOut,
    SellerSummaryOut,
)


def get_product(session: Session, product_id: int) -> ProductOut:
    row = session.execute(
        select(Product, Brand, Category, Seller)
        .join(Brand, Brand.id == Product.brand_id)
        .join(Category, Category.id == Product.category_id)
        .join(Seller, Seller.id == Product.seller_id)
        .where(Product.id == product_id)
    ).first()
    if row is None:
        raise NotFoundError("Product not found", code="product_not_found")
    p, brand, category, seller = row

    images = session.scalars(
        select(ProductImage)
        .where(ProductImage.product_id == p.id)
        .order_by(ProductImage.sort_order)
    )
    return ProductOut(
        id=p.id,
        sku=p.sku,
        title_ar=p.title_ar,
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
        images=[ProductImageOut.model_validate(i) for i in images],
        seller=SellerSummaryOut.model_validate(seller),
        brand=BrandOut.model_validate(brand),
        category=CategoryOut.model_validate(category),
    )
