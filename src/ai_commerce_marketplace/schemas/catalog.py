"""Public catalog response shapes (website). Matches the frontend's Product type.

Prices and ratings are Decimal, so they appear in JSON as exact strings ("9999.00").
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class _FromORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CategoryOut(_FromORM):
    id: int
    slug: str
    name_ar: str
    name_en: str
    spec_kind: str | None


class BrandOut(_FromORM):
    id: int
    slug: str
    name: str
    name_ar: str | None


class SellerSummaryOut(_FromORM):
    id: int
    store_name: str
    rating: Decimal | None


class ProductImageOut(_FromORM):
    url: str
    alt_ar: str | None


class ProductOut(BaseModel):
    id: int
    sku: str
    title_ar: str
    description_ar: str
    price_egp: Decimal
    old_price_egp: Decimal | None
    stock_qty: int
    warranty_months: int
    is_returnable: bool
    is_active: bool  # false = hidden by the seller; shown as "not available now"
    specs: dict[str, Any]
    rating_avg: Decimal | None
    rating_count: int
    created_at: datetime
    images: list[ProductImageOut]
    seller: SellerSummaryOut
    brand: BrandOut
    category: CategoryOut
