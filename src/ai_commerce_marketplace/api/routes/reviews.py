from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ai_commerce_marketplace.api.dependencies import require_role
from ai_commerce_marketplace.core.enums import Role
from ai_commerce_marketplace.database.models.user import User
from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.schemas.review import (
    ProductReviewsOut,
    ReviewableItemOut,
    ReviewIn,
    ReviewOut,
)
from ai_commerce_marketplace.services import reviews as svc
from ai_commerce_marketplace.services.reviews import MAX_LIMIT

router = APIRouter(tags=["reviews"])

customer_only = require_role(Role.CUSTOMER)


@router.get("/products/{product_id}/reviews", response_model=ProductReviewsOut)
def product_reviews(
    product_id: int,
    limit: int = Query(default=10, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    # public: anyone can read reviews on the product page
    return svc.product_reviews(session, product_id, limit, offset)


@router.post("/reviews", response_model=ReviewOut, status_code=201)
def create_review(
    data: ReviewIn,
    user: User = Depends(customer_only),
    session: Session = Depends(get_session),
):
    # customer id comes from the token; the item must be theirs and delivered
    return svc.create_review(session, user.id, data.order_item_id, data.rating, data.body)


@router.get("/reviews/mine", response_model=list[ReviewOut])
def my_reviews(
    user: User = Depends(customer_only),
    session: Session = Depends(get_session),
):
    return svc.my_reviews(session, user.id)


@router.get("/reviews/reviewable", response_model=list[ReviewableItemOut])
def reviewable_items(
    user: User = Depends(customer_only),
    session: Session = Depends(get_session),
):
    return svc.reviewable_items(session, user.id)
