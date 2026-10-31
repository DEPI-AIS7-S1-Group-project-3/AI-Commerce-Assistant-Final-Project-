from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from ai_commerce_marketplace.core.enums import SpecKind, enum_check
from ai_commerce_marketplace.database.base import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Identity(always=False), primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT")
    )
    slug: Mapped[str] = mapped_column(Text, unique=True)
    name_ar: Mapped[str] = mapped_column(Text)
    name_en: Mapped[str] = mapped_column(Text)
    spec_kind: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))

    __table_args__ = (
        CheckConstraint(enum_check("spec_kind", SpecKind), name="spec_kind"),
        Index("ix_categories_parent", "parent_id"),
    )


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(Identity(always=False), primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    name_ar: Mapped[str | None] = mapped_column(Text)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Identity(always=False), primary_key=True)
    seller_id: Mapped[int] = mapped_column(
        ForeignKey("sellers.id", ondelete="RESTRICT")
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT")
    )
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brands.id", ondelete="RESTRICT")
    )
    sku: Mapped[str] = mapped_column(Text, unique=True)
    title_ar: Mapped[str] = mapped_column(Text)
    description_ar: Mapped[str] = mapped_column(Text, server_default=text("''"))
    price_egp: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    old_price_egp: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    stock_qty: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    warranty_months: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    is_returnable: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    specs: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    search_text: Mapped[str] = mapped_column(Text, server_default=text("''"))
    rating_avg: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    rating_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("length(btrim(title_ar)) > 0", name="title_not_blank"),
        CheckConstraint("price_egp > 0", name="price_positive"),
        CheckConstraint(
            "old_price_egp IS NULL OR old_price_egp > price_egp", name="old_price"
        ),
        CheckConstraint("stock_qty >= 0", name="stock_non_negative"),
        CheckConstraint("warranty_months BETWEEN 0 AND 60", name="warranty_range"),
        CheckConstraint("jsonb_typeof(specs) = 'object'", name="specs_is_object"),
        CheckConstraint("rating_avg BETWEEN 0 AND 5", name="rating_avg_range"),
        CheckConstraint("rating_count >= 0", name="rating_count_non_negative"),
        Index(
            "ix_products_category_active",
            "category_id",
            postgresql_where=text("is_active"),
        ),
        Index("ix_products_brand", "brand_id"),
        Index("ix_products_seller", "seller_id"),
        Index("ix_products_price", "price_egp"),
        Index(
            "ix_products_specs_gin",
            "specs",
            postgresql_using="gin",
            postgresql_ops={"specs": "jsonb_path_ops"},
        ),
        Index(
            "ix_products_search_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
    )


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(Identity(always=False), primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE")
    )
    url: Mapped[str] = mapped_column(Text)
    alt_ar: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))

    __table_args__ = (UniqueConstraint("product_id", "sort_order"),)