from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from ai_commerce_marketplace.database.base import Base

TZ = TIMESTAMP(timezone=True)


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Identity(always=False), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZ, server_default=func.now(), onupdate=func.now()
    )


class CartItem(Base):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(Identity(always=False), primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE")
    )
    qty: Mapped[int] = mapped_column(Integer)
    added_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now())

    __table_args__ = (
        CheckConstraint("qty > 0", name="qty_positive"),
        UniqueConstraint("cart_id", "product_id"),
    )