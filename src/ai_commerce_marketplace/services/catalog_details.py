"""Read-only product detail and comparison for the Shopping Agent.

Decisions (agreed with the team):
- Inactive or out-of-stock products are still returned, with in_stock=False,
  so the agent can say "not available now".
- Brand shown is the Arabic name, falling back to the English name.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.agents.shopping.schemas import ProductDetail
from ai_commerce_marketplace.core.exceptions import NotFoundError
from ai_commerce_marketplace.database.models import Brand, Category, Product, ProductImage


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


def get_product(session: Session, product_id: int) -> ProductDetail:
    """Full detail for one product. Raises NotFoundError if the id does not exist."""
    row = session.execute(
        select(Product, Brand, Category)
        .join(Brand, Brand.id == Product.brand_id)
        .join(Category, Category.id == Product.category_id)
        .where(Product.id == product_id)
    ).first()
    if row is None:
        raise NotFoundError("Product not found", code="product_not_found")
    product, brand, category = row
    return _to_detail(session, product, brand, category)
