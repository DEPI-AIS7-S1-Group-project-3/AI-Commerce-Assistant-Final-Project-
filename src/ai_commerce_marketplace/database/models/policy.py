from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Identity,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from ai_commerce_marketplace.core.enums import PolicyCategory, enum_check
from ai_commerce_marketplace.database.base import Base


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(Identity(always=False), primary_key=True)
    slug: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    title_ar: Mapped[str] = mapped_column(Text)
    body_md: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    is_current: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(enum_check("category", PolicyCategory), name="category"),
        UniqueConstraint("slug", "version"),
        Index(
            "uq_policies_one_current",
            "slug",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )
