"""Shopping Agent search: wraps the public catalog listing and returns ProductCards."""

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from ai_commerce_marketplace.agents.shopping.schemas import ProductCard
from ai_commerce_marketplace.schemas.catalog import ProductOut
from ai_commerce_marketplace.services import catalog
from ai_commerce_marketplace.services.catalog import ProductSort


def _to_card(p: ProductOut) -> ProductCard:
    return ProductCard(
        id=p.id,
        title_ar=p.title_ar,
        brand=p.brand.name_ar or p.brand.name,
        category_slug=p.category.slug,
        price_egp=p.price_egp,
        old_price_egp=p.old_price_egp,
        rating_avg=p.rating_avg,
        rating_count=p.rating_count,
        in_stock=p.is_active and p.stock_qty > 0,
    )


def search_products(
    session: Session,
    *,
    query: str | None = None,
    category: str | None = None,
    brand: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    in_stock_only: bool = True,
    sort: ProductSort = "newest",
    specs: dict[str, Any] | None = None,
    sort_spec: str | None = None,
    limit: int = 5,
) -> list[ProductCard]:
    """Active products only. Out-of-stock ones appear (in_stock=False) when in_stock_only=False."""
    rows = catalog.list_products(
        session,
        q=query,
        category=category,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        in_stock=in_stock_only,
        sort=sort,
        specs=specs,
        sort_spec=sort_spec,
        limit=limit,
    )
    return [_to_card(p) for p in rows]
