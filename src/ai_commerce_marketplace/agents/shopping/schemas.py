"""Shared return shapes for the Shopping Agent tools.

Both people build on these. Change them only after agreeing with your teammate.
"""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class ProductCard(BaseModel):
    """Short product view used in search results and comparison rows."""

    id: int
    title_ar: str
    brand: str
    category_slug: str
    price_egp: Decimal
    old_price_egp: Decimal | None = None
    rating_avg: Decimal | None = None
    rating_count: int = 0
    in_stock: bool


class ProductDetail(ProductCard):
    """Full product view for product_get and products_compare."""

    description_ar: str
    warranty_months: int
    is_returnable: bool
    stock_qty: int
    specs: dict[str, Any]
    image_urls: list[str] = []
