"""Seed the database with synthetic demo data.

Deterministic and idempotent: running it twice does not duplicate rows.
Run:  uv run python scripts/seed_database.py
"""

import argparse
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from ai_commerce_marketplace.core.security import hash_password
from ai_commerce_marketplace.database.base import Base
from ai_commerce_marketplace.database.models import (
    Address,
    Brand,
    Cart,
    CartItem,
    Category,
    Order,
    OrderItem,
    OrderStatusHistory,
    Policy,
    Product,
    ProductImage,
    Return,
    Review,
    Seller,
    User,
)
from ai_commerce_marketplace.database.session import SessionLocal
from ai_commerce_marketplace.nlp.arabic import build_search_text
from ai_commerce_marketplace.schemas.specs import validate_specs

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


# ───────────── الجزء الثاني: المنتجات والطلبات والمراجعات والسياسات ─────────────
# الملفات دي متولّدة (deterministic) وتواريخها نسبية لـ anchor في _meta.json؛ الـ seed بيزحزحها
# كلها بنفس الفرق عشان «الطلب المتأخر» يفضل متأخر وقت العرض (--anchor-date، الافتراضي دلوقتي).


class _Ctx:
    """بيحل المفاتيح الطبيعية (email / sku / slug) إلى IDs، ويزحزح التواريخ."""

    def __init__(self, session, now: datetime) -> None:
        self.session = session
        meta = json.loads((DATA_DIR / "_meta.json").read_text(encoding="utf-8"))
        self.shift: timedelta = now - datetime.fromisoformat(meta["anchor"])
        self.users = {e.lower(): i for i, e in session.execute(select(User.id, User.email))}
        self.sellers = {
            e.lower(): sid
            for sid, e in session.execute(
                select(Seller.id, User.email).join(User, User.id == Seller.user_id)
            )
        }
        self.categories = {
            slug: cid for slug, cid in session.execute(select(Category.slug, Category.id))
        }
        self.brands = {b.slug: b for b in session.scalars(select(Brand))}

    def dt(self, value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) + self.shift if value else None

    def user(self, email: str | None) -> int | None:
        return self.users[email.lower()] if email else None

    def product_ids(self) -> dict[str, int]:
        return {sku: pid for sku, pid in self.session.execute(select(Product.sku, Product.id))}


def _money(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def seed_products(session, ctx: _Ctx) -> None:
    for p in _load("products.json"):
        brand = ctx.brands[p["brand_slug"]]
        category_slug = p["category_slug"]
        spec_kind = session.scalar(select(Category.spec_kind).where(Category.slug == category_slug))
        specs = validate_specs(spec_kind, p["specs"])  # لو فيه spec غلط الـ seed بيفشل
        created = ctx.dt(p["created_at"])
        row = {
            "seller_id": ctx.sellers[p["seller_email"].lower()],
            "category_id": ctx.categories[category_slug],
            "brand_id": brand.id,
            "sku": p["sku"],
            "title_ar": p["title_ar"],
            "description_ar": p["description_ar"],
            "price_egp": _money(p["price_egp"]),
            "old_price_egp": _money(p["old_price_egp"]),
            "stock_qty": p["stock_qty"],
            "warranty_months": p["warranty_months"],
            "is_returnable": p["is_returnable"],
            "is_active": p["is_active"],
            "specs": specs,
            "search_text": build_search_text(
                p["title_ar"], brand.name_ar, brand.name, p["description_ar"]
            ),
            "created_at": created,
            "updated_at": created,
        }
        product_id = session.scalar(
            insert(Product).values(row).on_conflict_do_nothing().returning(Product.id)
        )
        if product_id is None:  # موجود قبل كده: ما نلمسش بياناته (ممكن يكون اتعدّل)
            continue
        session.execute(
            insert(ProductImage).values([{"product_id": product_id, **img} for img in p["images"]])
        )


def seed_policies(session, ctx: _Ctx) -> None:
    for pol in _load("policies.json"):
        session.execute(insert(Policy).values(pol).on_conflict_do_nothing())


def seed_orders(session, ctx: _Ctx) -> None:
    products = ctx.product_ids()
    for o in _load("orders.json"):
        row = {
            "id": o["id"],
            "checkout_group_id": o["checkout_group_id"],
            "customer_id": ctx.user(o["customer_email"]),
            "seller_id": ctx.sellers[o["seller_email"].lower()],
            "status": o["status"],
            "payment_method": o["payment_method"],
            "payment_status": o["payment_status"],
            "shipping_address": o["shipping_address"],
            "subtotal_egp": _money(o["subtotal_egp"]),
            "shipping_fee_egp": _money(o["shipping_fee_egp"]),
            "total_egp": _money(o["total_egp"]),
            "expected_delivery_at": ctx.dt(o["expected_delivery_at"]),
            "delivered_at": ctx.dt(o["delivered_at"]),
            "cancelled_at": ctx.dt(o["cancelled_at"]),
            "cancel_reason_code": o["cancel_reason_code"],
            "created_at": ctx.dt(o["created_at"]),
            "updated_at": ctx.dt(o["updated_at"]),
        }
        inserted = session.scalar(
            insert(Order).values(row).on_conflict_do_nothing().returning(Order.id)
        )
        if inserted is None:  # الطلب موجود: items والـ history بتاعته موجودين برضه
            continue
        session.execute(
            insert(OrderItem).values(
                [
                    {
                        "order_id": o["id"],
                        "product_id": products[i["product_sku"]],
                        "product_title_snapshot": i["product_title_snapshot"],
                        "qty": i["qty"],
                        "unit_price_egp": _money(i["unit_price_egp"]),
                    }
                    for i in o["items"]
                ]
            )
        )
        session.execute(
            insert(OrderStatusHistory).values(
                [
                    {
                        "order_id": o["id"],
                        "from_status": h["from_status"],
                        "to_status": h["to_status"],
                        "actor_type": h["actor_type"],
                        "actor_user_id": ctx.user(h["actor_email"]),
                        "reason_code": h["reason_code"],
                        "note": h["note"],
                        "created_at": ctx.dt(h["created_at"]),
                    }
                    for h in o["status_history"]
                ]
            )
        )


def _order_item_id(session, products: dict[str, int], order_id: int, sku: str) -> int:
    return session.scalar(
        select(OrderItem.id).where(
            OrderItem.order_id == order_id, OrderItem.product_id == products[sku]
        )
    )


def seed_returns(session, ctx: _Ctx) -> None:
    products = ctx.product_ids()
    for r in _load("returns.json"):
        item_id = _order_item_id(session, products, r["order_id"], r["product_sku"])
        if session.scalar(select(Return.id).where(Return.order_item_id == item_id)):
            continue
        session.add(
            Return(
                order_item_id=item_id,
                requested_by=ctx.user(r["requested_by_email"]),
                qty=r["qty"],
                reason_code=r["reason_code"],
                reason_text=r["reason_text"],
                status=r["status"],
                created_at=ctx.dt(r["created_at"]),
                updated_at=ctx.dt(r["updated_at"]),
            )
        )
        session.flush()


def seed_reviews(session, ctx: _Ctx) -> None:
    products = ctx.product_ids()
    for r in _load("reviews.json"):
        item_id = _order_item_id(session, products, r["order_id"], r["product_sku"])
        row = {
            "product_id": products[r["product_sku"]],
            "customer_id": ctx.user(r["customer_email"]),
            "order_item_id": item_id,
            "rating": r["rating"],
            "body": r["body"],
            "is_verified_purchase": r["is_verified_purchase"],
            "created_at": ctx.dt(r["created_at"]),
        }
        session.execute(insert(Review).values(row).on_conflict_do_nothing())


def seed_carts(session, ctx: _Ctx) -> None:
    products = ctx.product_ids()
    for c in _load("carts.json"):
        user_id = ctx.user(c["customer_email"])
        cart_id = session.scalar(
            insert(Cart)
            .values(user_id=user_id, updated_at=ctx.dt(c["updated_at"]))
            .on_conflict_do_nothing()
            .returning(Cart.id)
        )
        if cart_id is None:
            continue
        for it in c["items"]:
            session.execute(
                insert(CartItem)
                .values(
                    cart_id=cart_id,
                    product_id=products[it["product_sku"]],
                    qty=it["qty"],
                    added_at=ctx.dt(it["added_at"]),
                )
                .on_conflict_do_nothing()
            )


def update_ratings(session) -> None:
    """rating_avg / rating_count للمنتجات، وrating للبائع، كلها محسوبة من جدول reviews."""
    session.execute(
        text(
            """
            UPDATE products p
               SET rating_avg = s.avg_rating, rating_count = s.cnt
              FROM (SELECT product_id, round(avg(rating)::numeric, 2) AS avg_rating, count(*) AS cnt
                      FROM reviews GROUP BY product_id) s
             WHERE p.id = s.product_id
            """
        )
    )
    session.execute(
        text(
            """
            UPDATE sellers
               SET rating = s.avg_rating
              FROM (SELECT p.seller_id, round(avg(r.rating)::numeric, 2) AS avg_rating
                      FROM reviews r JOIN products p ON p.id = r.product_id
                     GROUP BY p.seller_id) s
             WHERE sellers.id = s.seller_id
            """
        )
    )


def fix_sequences(session) -> None:
    """الـ identity مابتتحرّكش لما ندخل ID صريح (orders بـ 10001..): نظبط كل sequence على max(id)."""
    for table in Base.metadata.sorted_tables:
        if "id" not in table.c:
            continue
        session.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), max(id)) "  # noqa: S608
                f"FROM {table.name} HAVING max(id) IS NOT NULL"
            )
        )


def run(now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    with SessionLocal.begin() as session:  # transaction واحدة: يا كله يا ولا حاجة
        seed_categories(session)
        seed_brands(session)
        seed_users(session)
        seed_sellers(session)
        seed_addresses(session)
        ctx = _Ctx(session, now)
        seed_products(session, ctx)
        seed_policies(session, ctx)
        seed_orders(session, ctx)
        seed_returns(session, ctx)
        seed_reviews(session, ctx)
        seed_carts(session, ctx)
        update_ratings(session)
        fix_sequences(session)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the demo database")
    parser.add_argument(
        "--anchor-date",
        help="ISO date/time to treat as 'now' (default: the current time)",
    )
    args = parser.parse_args()
    now: Any = datetime.fromisoformat(args.anchor_date) if args.anchor_date else None
    if now is not None and now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    run(now)
    with SessionLocal() as session:
        for model in (
            Category,
            Brand,
            User,
            Seller,
            Address,
            Product,
            ProductImage,
            Order,
            OrderItem,
            OrderStatusHistory,
            Return,
            Review,
            Cart,
            CartItem,
            Policy,
        ):
            count = session.scalar(select(func.count()).select_from(model))
            print(f"{model.__tablename__:<22} {count}")


if __name__ == "__main__":
    main()
