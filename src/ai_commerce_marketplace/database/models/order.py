import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Computed,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from ai_commerce_marketplace.core.enums import (
    ActorType,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    ReturnReason,
    ReturnStatus,
    enum_check,
)
from ai_commerce_marketplace.database.base import Base

TZ = TIMESTAMP(timezone=True)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(
        Identity(always=False, start=10001), primary_key=True
    )
    checkout_group_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    seller_id: Mapped[int] = mapped_column(
        ForeignKey("sellers.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    payment_method: Mapped[str] = mapped_column(Text)
    payment_status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    shipping_address: Mapped[dict[str, Any]] = mapped_column(JSONB)
    subtotal_egp: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    shipping_fee_egp: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), server_default=text("0")
    )
    total_egp: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    expected_delivery_at: Mapped[datetime] = mapped_column(TZ)
    delivered_at: Mapped[datetime | None] = mapped_column(TZ)
    cancelled_at: Mapped[datetime | None] = mapped_column(TZ)
    cancel_reason_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TZ, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(enum_check("status", OrderStatus), name="status"),
        CheckConstraint(
            enum_check("payment_method", PaymentMethod), name="payment_method"
        ),
        CheckConstraint(
            enum_check("payment_status", PaymentStatus), name="payment_status"
        ),
        CheckConstraint("subtotal_egp >= 0", name="subtotal_non_negative"),
        CheckConstraint("shipping_fee_egp >= 0", name="shipping_fee_non_negative"),
        CheckConstraint("total_egp = subtotal_egp + shipping_fee_egp", name="total"),
        CheckConstraint(
            "(status IN ('delivered','return_requested','returned')) "
            "= (delivered_at IS NOT NULL)",
            name="delivered",
        ),
        CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL)", name="cancelled"
        ),
        CheckConstraint(
            "delivered_at IS NULL OR delivered_at >= created_at", name="dates"
        ),
        CheckConstraint("jsonb_typeof(shipping_address) = 'object'", name="addr"),
        Index("ix_orders_customer", "customer_id", text("created_at DESC")),
        Index("ix_orders_seller", "seller_id", text("created_at DESC")),
        Index("ix_orders_seller_status", "seller_id", "status"),
        Index("ix_orders_group", "checkout_group_id"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Identity(always=False), primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT")
    )
    product_title_snapshot: Mapped[str] = mapped_column(Text)
    qty: Mapped[int] = mapped_column(Integer)
    unit_price_egp: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # عمود محسوب في الـ DB (nullable=True عشان يطابق الـ DDL بالظبط)
    line_total_egp: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        Computed("qty * unit_price_egp", persisted=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint("qty > 0", name="qty_positive"),
        CheckConstraint("unit_price_egp > 0", name="unit_price_positive"),
        UniqueConstraint("order_id", "product_id"),
        Index("ix_order_items_product", "product_id"),
    )


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(Identity(always=False), primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    from_status: Mapped[str | None] = mapped_column(Text)
    to_status: Mapped[str] = mapped_column(Text)
    actor_type: Mapped[str] = mapped_column(Text)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reason_code: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now())

    __table_args__ = (
        CheckConstraint(enum_check("actor_type", ActorType), name="actor_type"),
        Index("ix_osh_order", "order_id", "created_at"),
    )


class Return(Base):
    __tablename__ = "returns"

    id: Mapped[int] = mapped_column(Identity(always=False), primary_key=True)
    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id", ondelete="CASCADE")
    )
    requested_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    qty: Mapped[int] = mapped_column(Integer)
    reason_code: Mapped[str] = mapped_column(Text)
    reason_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'requested'"))
    created_at: Mapped[datetime] = mapped_column(TZ, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TZ, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("qty > 0", name="qty_positive"),
        CheckConstraint(enum_check("reason_code", ReturnReason), name="reason_code"),
        CheckConstraint(enum_check("status", ReturnStatus), name="status"),
        Index(
            "uq_returns_one_active_per_item",
            "order_item_id",
            unique=True,
            postgresql_where=text("status IN ('requested','approved','received')"),
        ),
    )