from decimal import Decimal

from pydantic import BaseModel, Field


class CartItemIn(BaseModel):
    product_id: int
    qty: int = Field(default=1, ge=1, le=100)


class CartQtyIn(BaseModel):
    qty: int = Field(ge=1, le=100)


class CartItemOut(BaseModel):
    product_id: int
    title_ar: str
    qty: int
    unit_price_egp: Decimal
    line_total_egp: Decimal
    stock_qty: int
    available: bool  # false if the product was deactivated or stock dropped below qty


class CartOut(BaseModel):
    items: list[CartItemOut]
    subtotal_egp: Decimal  # computed on the server, available items only
