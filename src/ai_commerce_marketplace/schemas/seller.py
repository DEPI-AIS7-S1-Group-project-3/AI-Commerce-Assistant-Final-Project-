"""Seller dashboard + seller orders (GET /seller/..., POST /seller/orders/{id}/status)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class Kpis(BaseModel):
    revenue: Decimal
    units_sold: int
    orders_count: int
    aov: Decimal


class KpiChange(BaseModel):
    """Current period vs the period just before it (same length)."""

    revenue_pct: Decimal | None  # None when the previous period was 0
    units_sold_pct: Decimal | None
    orders_count_pct: Decimal | None
    aov_pct: Decimal | None


class DailyPoint(BaseModel):
    day: date  # Cairo calendar day
    revenue: Decimal
    orders: int


class TopProduct(BaseModel):
    product_id: int
    title: str
    units_sold: int
    revenue: Decimal


class LowStockProduct(BaseModel):
    product_id: int
    title: str
    stock_qty: int


class SellerDashboardOut(BaseModel):
    store_name: str
    days: int
    kpis: Kpis
    change: KpiChange
    daily: list[DailyPoint]
    top_products: list[TopProduct]
    low_stock: list[LowStockProduct]
    orders_by_status: dict[str, int]
    pending_actions: int  # orders the seller still has to move forward (not delivered yet)


class SellerOrderItemOut(BaseModel):
    product_id: int
    title: str
    qty: int
    line_total_egp: Decimal


class SellerOrderOut(BaseModel):
    id: int
    created_at: datetime
    status: str
    next_status: str | None  # the one forward step the seller may take now
    payment_method: str
    payment_status: str
    customer_name: str  # first name only
    governorate: str | None
    city: str | None
    subtotal_egp: Decimal
    shipping_fee_egp: Decimal
    total_egp: Decimal
    expected_delivery_at: datetime
    delivered_at: datetime | None
    items: list[SellerOrderItemOut]


class StatusIn(BaseModel):
    # forward steps only (see services/seller_dashboard.NEXT); cancel is the customer's action
    to_status: Literal["confirmed", "shipped", "out_for_delivery", "delivered"]


# ---- products (stage B: inventory) ----
class SellerProductOut(BaseModel):
    id: int
    sku: str
    title_ar: str
    title_en: str | None
    category_slug: str
    brand: str
    price_egp: Decimal
    old_price_egp: Decimal | None
    stock_qty: int
    is_active: bool
    rating_avg: Decimal | None
    rating_count: int
    image_url: str | None


class ProductPatchIn(BaseModel):
    """Only the fields sent are changed. Send old_price_egp: null to remove the old price."""

    price_egp: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    old_price_egp: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    stock_qty: int | None = Field(default=None, ge=0, le=100_000)
    is_active: bool | None = None
