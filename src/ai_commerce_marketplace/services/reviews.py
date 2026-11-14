"""Product reviews: only a customer who received the item can review it, once per order item."""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.exceptions import ConflictError, NotFoundError
from ai_commerce_marketplace.database.models.catalog import Product
from ai_commerce_marketplace.database.models.order import Order, OrderItem
from ai_commerce_marketplace.database.models.review import Review
from ai_commerce_marketplace.database.models.seller import Seller
from ai_commerce_marketplace.database.models.user import User
from ai_commerce_marketplace.schemas.review import (
    ProductReviewsOut,
    ReviewableItemOut,
    ReviewOut,
)

MAX_LIMIT = 50


def _first_name(full_name: str) -> str:
    return full_name.split()[0] if full_name.strip() else ""


def _out(review: Review, author: str) -> ReviewOut:
    return ReviewOut(
        id=review.id,
        product_id=review.product_id,
        order_item_id=review.order_item_id,
        rating=review.rating,
        body=review.body,
        author_name=_first_name(author),
        is_verified_purchase=review.is_verified_purchase,
        created_at=review.created_at,
    )


def _refresh_ratings(session: Session, product: Product) -> None:
    """Same formulas as the seed: product avg/count, seller avg over all its products' reviews."""
    avg, count = session.execute(
        select(func.round(func.avg(Review.rating), 2), func.count()).where(
            Review.product_id == product.id
        )
    ).one()
    product.rating_avg = Decimal(avg) if avg is not None else None
    product.rating_count = count

    seller_avg = session.scalar(
        select(func.round(func.avg(Review.rating), 2))
        .join(Product, Product.id == Review.product_id)
        .where(Product.seller_id == product.seller_id)
    )
    seller = session.get(Seller, product.seller_id)
    if seller is not None:
        seller.rating = Decimal(seller_avg) if seller_avg is not None else None


def create_review(
    session: Session, customer_id: int, order_item_id: int, rating: int, body: str
) -> ReviewOut:
    try:
        row = session.execute(
            select(OrderItem, Order)
            .join(Order, Order.id == OrderItem.order_id)
            .where(OrderItem.id == order_item_id, Order.customer_id == customer_id)
        ).first()
        if row is None:
            raise NotFoundError("Order item not found", code="order_item_not_found")
        item, order = row
        if order.delivered_at is None:
            raise ConflictError(
                "You can review a product only after it is delivered", code="not_delivered"
            )
        if session.scalar(select(Review.id).where(Review.order_item_id == item.id)):
            raise ConflictError("You already reviewed this item", code="review_exists")

        # lock the product so two reviews at once still give the right average
        product = session.scalar(
            select(Product).where(Product.id == item.product_id).with_for_update()
        )
        assert product is not None
        review = Review(
            product_id=item.product_id,
            customer_id=customer_id,
            order_item_id=item.id,
            rating=rating,
            body=body.strip(),
            is_verified_purchase=True,
        )
        session.add(review)
        try:
            session.flush()
        except IntegrityError:
            raise ConflictError("You already reviewed this item", code="review_exists") from None
        _refresh_ratings(session, product)
        session.commit()
        author = session.scalar(select(User.full_name).where(User.id == customer_id)) or ""
        return _out(review, author)
    except Exception:
        session.rollback()
        raise


def product_reviews(
    session: Session, product_id: int, limit: int = 10, offset: int = 0
) -> ProductReviewsOut:
    product = session.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found", code="product_not_found")
    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)

    dist = {str(n): 0 for n in range(1, 6)}
    for rating, count in session.execute(
        select(Review.rating, func.count())
        .where(Review.product_id == product_id)
        .group_by(Review.rating)
    ):
        dist[str(rating)] = count

    rows = session.execute(
        select(Review, User.full_name)
        .join(User, User.id == Review.customer_id)
        .where(Review.product_id == product_id)
        .order_by(Review.created_at.desc(), Review.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ProductReviewsOut(
        product_id=product.id,
        rating_avg=product.rating_avg,
        rating_count=product.rating_count,
        distribution=dist,
        total=sum(dist.values()),
        reviews=[_out(r, name) for r, name in rows],
    )


def my_reviews(session: Session, customer_id: int) -> list[ReviewOut]:
    rows = session.execute(
        select(Review, User.full_name)
        .join(User, User.id == Review.customer_id)
        .where(Review.customer_id == customer_id)
        .order_by(Review.created_at.desc(), Review.id.desc())
    ).all()
    return [_out(r, name) for r, name in rows]


def reviewable_items(session: Session, customer_id: int) -> list[ReviewableItemOut]:
    """Items the customer received and has not reviewed yet (for the review form)."""
    rows = session.execute(
        select(OrderItem, Order)
        .join(Order, Order.id == OrderItem.order_id)
        .outerjoin(Review, Review.order_item_id == OrderItem.id)
        .where(
            Order.customer_id == customer_id,
            Order.delivered_at.is_not(None),
            Review.id.is_(None),
        )
        .order_by(Order.delivered_at.desc(), OrderItem.id)
    ).all()
    return [
        ReviewableItemOut(
            order_id=order.id,
            order_item_id=item.id,
            product_id=item.product_id,
            title=item.product_title_snapshot,
            delivered_at=order.delivered_at,
        )
        for item, order in rows
        if order.delivered_at is not None
    ]
