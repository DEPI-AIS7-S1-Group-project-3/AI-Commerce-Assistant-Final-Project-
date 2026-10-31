"""Seed the database with synthetic demo data.

Deterministic and idempotent: running it twice does not duplicate rows.
Run:  uv run python scripts/seed_database.py
"""
import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from ai_commerce_marketplace.core.security import hash_password
from ai_commerce_marketplace.database.models import (
    Address,
    Brand,
    Category,
    Seller,
    User,
)
from ai_commerce_marketplace.database.session import SessionLocal

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
DEMO_PASSWORD = "Demo@12345"  # للتطوير فقط، موثّق في الـ README


def _load(name: str) -> list[dict]:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def _insert_ignore(session, model, rows: list[dict]) -> None:
    if rows:
        session.execute(insert(model).values(rows).on_conflict_do_nothing())


def _user_id(session, email: str) -> int:
    return session.scalar(select(User.id).where(func.lower(User.email) == email.lower()))


def seed_categories(session) -> None:
    for row in _load("categories.json"):  # الأب قبل الأبناء في الملف
        parent_slug = row.pop("parent_slug")
        row["parent_id"] = (
            session.scalar(select(Category.id).where(Category.slug == parent_slug))
            if parent_slug
            else None
        )
        _insert_ignore(session, Category, [row])


def seed_brands(session) -> None:
    _insert_ignore(session, Brand, _load("brands.json"))


def seed_users(session) -> None:
    password_hash = hash_password(DEMO_PASSWORD)
    rows = [{**u, "password_hash": password_hash} for u in _load("users.json")]
    _insert_ignore(session, User, rows)


def seed_sellers(session) -> None:
    rows = []
    for s in _load("sellers.json"):
        email = s.pop("user_email")
        rows.append({**s, "user_id": _user_id(session, email)})
    _insert_ignore(session, Seller, rows)


def seed_addresses(session) -> None:
    for a in _load("addresses.json"):
        user_id = _user_id(session, a.pop("user_email"))
        exists = session.scalar(
            select(Address.id).where(
                Address.user_id == user_id,
                Address.street_address == a["street_address"],
            )
        )
        if not exists:
            session.add(Address(user_id=user_id, **a))
            session.flush()


def run() -> None:
    with SessionLocal.begin() as session:  # transaction واحدة: يا كله يا ولا حاجة
        seed_categories(session)
        seed_brands(session)
        seed_users(session)
        seed_sellers(session)
        seed_addresses(session)


def main() -> None:
    run()
    with SessionLocal() as session:
        for model in (Category, Brand, User, Seller, Address):
            count = session.scalar(select(func.count()).select_from(model))
            print(f"{model.__tablename__:<12} {count}")


if __name__ == "__main__":
    main()