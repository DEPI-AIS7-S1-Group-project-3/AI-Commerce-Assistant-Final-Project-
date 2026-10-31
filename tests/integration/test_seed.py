import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from ai_commerce_marketplace.core.security import verify_password
from ai_commerce_marketplace.database.base import Base
from ai_commerce_marketplace.database.models import (
    Address,
    Brand,
    Category,
    Seller,
    User,
)
from ai_commerce_marketplace.database.session import SessionLocal, engine

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def seed(migrated_db):
    spec = importlib.util.spec_from_file_location(
        "seed_database", ROOT / "scripts" / "seed_database.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    # تنضيف: الـ seed بيعمل commit حقيقي، فنفضّي الجداول بعد الاختبارات
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


def _count(model) -> int:
    with SessionLocal() as s:
        return s.scalar(select(func.count()).select_from(model))


def test_base_counts(seed):
    seed.run()
    assert _count(Category) == 4
    assert _count(Brand) == 12
    assert _count(User) == 16
    assert _count(Seller) == 4
    assert _count(Address) >= 12


def test_seed_is_idempotent(seed):
    seed.run()
    before = [_count(m) for m in (Category, Brand, User, Seller, Address)]
    seed.run()
    after = [_count(m) for m in (Category, Brand, User, Seller, Address)]
    assert before == after


def test_users_are_demo_only(seed):
    seed.run()
    with SessionLocal() as s:
        emails = s.scalars(select(User.email)).all()
        assert all(e.endswith("@example.com") for e in emails)
        user = s.scalars(select(User)).first()
        assert verify_password(user.password_hash, seed.DEMO_PASSWORD)


def test_every_customer_has_exactly_one_default_address(seed):
    seed.run()
    with SessionLocal() as s:
        customers = s.scalars(select(User.id).where(User.role == "customer")).all()
        for uid in customers:
            n = s.scalar(
                select(func.count())
                .select_from(Address)
                .where(Address.user_id == uid, Address.is_default)
            )
            assert n == 1


def test_addresses_cover_required_cities(seed):
    seed.run()
    with SessionLocal() as s:
        cities = set(s.scalars(select(Address.city)).all())
        govs = set(s.scalars(select(Address.governorate)).all())
    assert {"القاهرة", "الإسكندرية", "أسيوط"} <= govs
    assert "المنصورة" in cities
