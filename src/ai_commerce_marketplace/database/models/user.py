from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from ai_commerce_marketplace.core.enums import Role, enum_check
from ai_commerce_marketplace.database.base import Base

PHONE_REGEX = "phone ~ '^01[0125][0-9]{8}$'"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Identity(always=False), primary_key=True)
    role: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text)
    phone: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(enum_check("role", Role), name="role"),
        CheckConstraint("length(btrim(full_name)) > 0", name="full_name_not_blank"),
        CheckConstraint(PHONE_REGEX, name="phone_format"),
        Index("uq_users_email_lower", text("lower(email)"), unique=True),
    )


class Address(Base):
    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(Identity(always=False), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    label: Mapped[str | None] = mapped_column(Text)
    recipient_name: Mapped[str] = mapped_column(Text)
    phone: Mapped[str] = mapped_column(Text)
    governorate: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(Text)
    street_address: Mapped[str] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(PHONE_REGEX, name="phone_format"),
        Index("ix_addresses_user", "user_id"),
        Index(
            "uq_addresses_one_default",
            "user_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )