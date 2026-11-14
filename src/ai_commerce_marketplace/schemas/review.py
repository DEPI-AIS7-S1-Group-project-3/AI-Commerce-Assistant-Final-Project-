from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

MAX_BODY = 2000


class ReviewIn(BaseModel):
    order_item_id: int
    rating: int = Field(ge=1, le=5)
    body: str = Field(default="", max_length=MAX_BODY)


class ReviewOut(BaseModel):
    id: int
    product_id: int
    order_item_id: int
    rating: int
    body: str
    author_name: str  # first name only
    is_verified_purchase: bool
    created_at: datetime


class ProductReviewsOut(BaseModel):
    product_id: int
    rating_avg: Decimal | None
    rating_count: int
    distribution: dict[str, int]  # "1".."5" -> count
    total: int
    reviews: list[ReviewOut]


class ReviewableItemOut(BaseModel):
    """A delivered item the customer has not reviewed yet."""

    order_id: int
    order_item_id: int
    product_id: int
    title: str
    delivered_at: datetime
