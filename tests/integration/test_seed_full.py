"""Tests for the full demo data: catalog, orders, returns, reviews, policies.

They run the real seed script against the test database and check the data is consistent
(totals, status history, dates, review and return rules, search, sequences).
"""

import importlib.util
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from ai_commerce_marketplace.database.base import Base
from ai_commerce_marketplace.database.models import (
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
from ai_commerce_marketplace.database.session import SessionLocal, engine
from ai_commerce_marketplace.nlp.arabic import normalize_ar
from ai_commerce_marketplace.schemas.specs import validate_specs
from ai_commerce_marketplace.services.order_rules import (
    check_cancel_eligibility,
    check_return_eligibility,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def seeded(migrated_db):
    spec = importlib.util.spec_from_file_location(
        "seed_database_full", ROOT / "scripts" / "seed_database.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.run()
    yield module
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


def _count(model) -> int:
    with SessionLocal() as s:
        return s.scalar(select(func.count()).select_from(model))


MODELS = (
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
)


def test_counts(seeded):
    with SessionLocal() as s:
        per_category = dict(
            s.execute(
                select(Category.slug, func.count(Product.id))
                .join(Product, Product.category_id == Category.id)
                .group_by(Category.slug)
            ).all()
        )
        assert per_category == {"mobiles": 15, "laptops": 15, "audio": 15}
        assert s.scalar(select(func.count()).where(Product.is_active.is_(False))) == 3
        assert s.scalar(select(func.count()).where(Product.stock_qty == 0)) >= 2
        assert s.scalar(select(func.count()).where(Product.is_returnable.is_(False))) >= 1
    assert _count(Order) == 120
    assert _count(Review) >= 80
    assert _count(Policy) == 4


def test_seed_twice_does_not_duplicate(seeded):
    before = [_count(m) for m in MODELS]
    seeded.run()
    assert [_count(m) for m in MODELS] == before


def test_every_product_spec_is_valid_and_seller_is_multi_category(seeded):
    with SessionLocal() as s:
        for p, kind in s.execute(
            select(Product, Category.spec_kind).join(Category, Category.id == Product.category_id)
        ):
            validate_specs(kind, p.specs)
            assert p.price_egp > 0 and p.stock_qty >= 0
        for seller_id in s.scalars(select(Seller.id)):
            n = s.scalar(
                select(func.count(func.distinct(Product.category_id))).where(
                    Product.seller_id == seller_id
                )
            )
            assert n >= 2


def test_product_search_text_is_normalized_arabic(seeded):
    with SessionLocal() as s:
        for p in s.scalars(select(Product)):
            assert p.search_text == normalize_ar(p.search_text) and p.search_text
        # لازم البحث بالعربي (بعد التطبيع) يلاقي لابتوبات وسماعات
        for word in ("لابتوب", "سماعه", "باور بانك"):
            hits = s.scalar(
                select(func.count()).where(Product.search_text.like(f"%{normalize_ar(word)}%"))
            )
            assert hits > 0, word


def test_order_totals_and_shipping_rules(seeded):
    with SessionLocal() as s:
        for o in s.scalars(select(Order)):
            subtotal = s.scalar(
                select(func.sum(OrderItem.line_total_egp)).where(OrderItem.order_id == o.id)
            )
            assert o.subtotal_egp == subtotal
            assert o.total_egp == o.subtotal_egp + o.shipping_fee_egp
            assert o.shipping_fee_egp == (0 if o.subtotal_egp >= 5000 else 60)
            days = (
                2 if o.shipping_address["governorate"] in {"القاهرة", "الجيزة", "الإسكندرية"} else 4
            )
            # بالـ UTC عشان تغيير التوقيت الصيفي في القاهرة مايأثرش على الحساب
            expected = o.created_at.astimezone(UTC) + timedelta(days=days)
            assert o.expected_delivery_at.astimezone(UTC) == expected
            # كل منتجات الطلب من نفس بائع الطلب
            other = s.scalar(
                select(func.count())
                .select_from(OrderItem)
                .join(Product, Product.id == OrderItem.product_id)
                .where(OrderItem.order_id == o.id, Product.seller_id != o.seller_id)
            )
            assert other == 0


def test_status_history_matches_current_status_and_dates(seeded):
    now = datetime.now(UTC)
    with SessionLocal() as s:
        for o in s.scalars(select(Order)):
            hist = s.scalars(
                select(OrderStatusHistory)
                .where(OrderStatusHistory.order_id == o.id)
                .order_by(OrderStatusHistory.id)
            ).all()
            assert hist[0].from_status is None and hist[0].to_status == "pending"
            assert hist[-1].to_status == o.status
            for prev, cur in zip(hist, hist[1:], strict=False):
                assert cur.from_status == prev.to_status
                assert cur.created_at >= prev.created_at
            assert max(o.created_at, *(h.created_at for h in hist)) <= now
            if o.delivered_at:
                assert o.delivered_at >= o.created_at
            # الإلغاء قبل الشحن بس (مفيش استثناء للتأخير)
            if o.status == "cancelled":
                assert not {h.to_status for h in hist} & {"shipped", "out_for_delivery"}


def test_multi_seller_checkouts_share_group_id(seeded):
    with SessionLocal() as s:
        groups = s.execute(
            select(
                Order.checkout_group_id, func.count(), func.count(func.distinct(Order.seller_id))
            )
            .group_by(Order.checkout_group_id)
            .having(func.count() > 1)
        ).all()
        assert len(groups) >= 5
        assert all(n == sellers for _, n, sellers in groups)


def test_demo_orders_have_the_documented_scenarios(seeded):
    now = datetime.now(UTC)
    with SessionLocal() as s:
        o = {i: s.get(Order, i) for i in range(10001, 10006)}
        customers = {x.customer_id for x in o.values()}
        assert len(customers) == 5  # كل واحد لعميل مختلف
        # 10001: متأخر في الطريق (الموعد قبل 5 أيام) وبالكارت، والإلغاء مرفوض
        assert o[10001].status == "out_for_delivery" and o[10001].payment_method == "card"
        assert abs((now - o[10001].expected_delivery_at) - timedelta(days=5)) < timedelta(minutes=5)
        assert not check_cancel_eligibility(o[10001].status, now).allowed
        # 10002: confirmed و cod، وبيتلغي
        assert o[10002].status == "confirmed" and o[10002].payment_method == "cod"
        assert check_cancel_eligibility(o[10002].status, now).allowed
        # 10003: اتسلّم قبل 3 أيام والمنتج قابل للإرجاع
        assert o[10003].status == "delivered"
        assert abs((now - o[10003].delivered_at) - timedelta(days=3)) < timedelta(minutes=5)
        item = s.scalars(select(OrderItem).where(OrderItem.order_id == 10003)).one()
        assert s.get(Product, item.product_id).is_returnable
        assert check_return_eligibility(
            "delivered", o[10003].delivered_at, True, False, now
        ).allowed
        # 10004: اتسلّم قبل 31 يوم والإرجاع مرفوض
        assert abs((now - o[10004].delivered_at) - timedelta(days=31)) < timedelta(minutes=5)
        result = check_return_eligibility("delivered", o[10004].delivered_at, True, False, now)
        assert not result.allowed and result.code == "window_expired"
        # 10005: ملغي بسبب customer_request ومعاه history كامل
        assert o[10005].status == "cancelled" and o[10005].cancel_reason_code == "customer_request"
        reasons = s.scalars(
            select(OrderStatusHistory.reason_code).where(
                OrderStatusHistory.order_id == 10005, OrderStatusHistory.to_status == "cancelled"
            )
        ).all()
        assert reasons == ["customer_request"]


def test_returns_follow_the_rules(seeded):
    with SessionLocal() as s:
        rows = s.execute(
            select(Return, OrderItem, Order, Product)
            .join(OrderItem, OrderItem.id == Return.order_item_id)
            .join(Order, Order.id == OrderItem.order_id)
            .join(Product, Product.id == OrderItem.product_id)
        ).all()
        assert len(rows) >= 14
        statuses = {r.status for r, *_ in rows}
        assert {"requested", "rejected"} <= statuses and statuses & {"refunded", "received"}
        for ret, item, order, product in rows:
            assert product.is_returnable and ret.qty <= item.qty
            assert ret.created_at <= order.delivered_at + timedelta(days=14)
            expected = {"requested": "return_requested", "rejected": "delivered"}.get(
                ret.status, "returned"
            )
            assert order.status == expected


def test_reviews_only_on_delivered_or_returned_items(seeded):
    with SessionLocal() as s:
        rows = s.execute(
            select(Review, Order)
            .join(OrderItem, OrderItem.id == Review.order_item_id)
            .join(Order, Order.id == OrderItem.order_id)
        ).all()
        for review, order in rows:
            assert order.status in {"delivered", "returned"}
            assert review.customer_id == order.customer_id and review.body
            assert review.created_at >= order.delivered_at
        assert {r.rating for r, _ in rows} >= {2, 3, 4, 5}


def test_rating_aggregates_match_reviews(seeded):
    with SessionLocal() as s:
        for p in s.scalars(select(Product)):
            n, avg = s.execute(
                select(func.count(), func.avg(Review.rating)).where(Review.product_id == p.id)
            ).one()
            assert p.rating_count == n
            assert (p.rating_avg is None) == (n == 0)
            if n:
                assert abs(float(p.rating_avg) - float(avg)) < 0.01
        for seller in s.scalars(select(Seller)):
            assert seller.rating is not None and 1 <= seller.rating <= 5


def test_seller_trends_exist_for_period_comparison(seeded):
    now = datetime.now(UTC)
    with SessionLocal() as s:

        def counts(seller_id: int) -> tuple[int, int]:
            recent = s.scalar(
                select(func.count()).where(
                    Order.seller_id == seller_id, Order.created_at >= now - timedelta(days=30)
                )
            )
            previous = s.scalar(
                select(func.count()).where(
                    Order.seller_id == seller_id,
                    Order.created_at < now - timedelta(days=30),
                    Order.created_at >= now - timedelta(days=60),
                )
            )
            return recent, previous

        ids = {
            e: s.scalar(
                select(Seller.id).join(User, User.id == Seller.user_id).where(User.email == e)
            )
            for e in ("seller1@example.com", "seller3@example.com")
        }
        up_recent, up_prev = counts(ids["seller1@example.com"])
        down_recent, down_prev = counts(ids["seller3@example.com"])
        assert up_recent > up_prev
        assert down_recent < down_prev


def test_policies_are_numbered_arabic_sections(seeded):
    with SessionLocal() as s:
        policies = {p.slug: p for p in s.scalars(select(Policy))}
        assert set(policies) == {"shipping", "returns", "warranty", "cancellation"}
        for p in policies.values():
            assert p.is_current and p.is_demo and "## 1." in p.body_md
        assert "14" in policies["returns"].body_md
        # مفيش استثناء إلغاء بعد التأخير في السياسات
        assert "تأخر التوصيل" not in policies["cancellation"].body_md
        assert "5000" in policies["shipping"].body_md and "60" in policies["shipping"].body_md


def test_new_order_after_seed_gets_a_fresh_id(seeded):
    """فخ الـ identity: من غير setval أول طلب جديد بعد الـ seed كان هيفشل بـ duplicate key."""
    with SessionLocal() as s:
        customer = s.scalar(select(User.id).where(User.role == "customer"))
        seller = s.scalar(select(Seller.id))
        max_id = s.scalar(select(func.max(Order.id)))
        order = Order(
            checkout_group_id=uuid.uuid4(),
            customer_id=customer,
            seller_id=seller,
            payment_method="cod",
            shipping_address={"city": "x"},
            subtotal_egp=100,
            shipping_fee_egp=60,
            total_egp=160,
            expected_delivery_at=datetime.now(UTC) + timedelta(days=2),
        )
        s.add(order)
        s.flush()
        assert order.id > max_id
        s.rollback()  # ما نسيبش طلب زيادة في الـ DB


def test_all_sequences_are_ahead_of_seeded_ids(seeded):
    with SessionLocal() as s:
        for table in Base.metadata.sorted_tables:
            if "id" not in table.c:
                continue
            max_id = s.scalar(text(f"SELECT max(id) FROM {table.name}"))  # noqa: S608
            if max_id is None:
                continue
            seq = s.scalar(text(f"SELECT pg_get_serial_sequence('{table.name}', 'id')"))
            last = s.scalar(text(f"SELECT last_value FROM {seq}"))  # noqa: S608
            assert last >= max_id, table.name
