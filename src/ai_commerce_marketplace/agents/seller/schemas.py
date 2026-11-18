from decimal import Decimal

from pydantic import BaseModel


class SalesSummary(BaseModel):
    date_from: str
    date_to: str
    revenue: Decimal
    units_sold: int
    orders_count: int
    aov: Decimal


class MetricChange(BaseModel):
    a: Decimal
    b: Decimal
    delta: Decimal
    change_pct: Decimal | None = None  # None when the baseline (a) is 0


class PeriodRange(BaseModel):
    date_from: str
    date_to: str


class PeriodComparison(BaseModel):
    period_a: PeriodRange
    period_b: PeriodRange
    revenue: MetricChange
    units_sold: MetricChange
    orders_count: MetricChange
    aov: MetricChange


class TopProduct(BaseModel):
    product_id: int
    title: str
    units_sold: int
    revenue: Decimal


class LowStockProduct(BaseModel):
    product_id: int
    title: str
    stock_qty: int


class ReturnsReport(BaseModel):
    total_returns: int
    by_reason: dict[str, int]


class ProductReviews(BaseModel):
    product_id: int
    rating_avg: float | None = None
    reviews_count: int
    recent_low_rated: list[str]
