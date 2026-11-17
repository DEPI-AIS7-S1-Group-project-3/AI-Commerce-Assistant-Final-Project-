from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ai_commerce_marketplace.api.dependencies import require_role
from ai_commerce_marketplace.core.enums import OrderStatus, Role
from ai_commerce_marketplace.database.models.user import User
from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.schemas.seller import (
    ProductPatchIn,
    SellerDashboardOut,
    SellerOrderOut,
    SellerProductOut,
    StatusIn,
)
from ai_commerce_marketplace.services import seller_dashboard as svc
from ai_commerce_marketplace.services import seller_products as products_svc
from ai_commerce_marketplace.services.seller_analytics import seller_id_for_user

# Every route: seller login required; the seller id comes from the token, never from the request.
router = APIRouter(prefix="/seller", tags=["seller"])
seller_only = require_role(Role.SELLER)


@router.get("/dashboard", response_model=SellerDashboardOut)
def dashboard(
    days: Annotated[int, Query(ge=7, le=90)] = 30,
    user: User = Depends(seller_only),
    session: Session = Depends(get_session),
):
    return svc.dashboard(session, seller_id_for_user(session, user.id), days)


@router.get("/orders", response_model=list[SellerOrderOut])
def list_orders(
    status: OrderStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: User = Depends(seller_only),
    session: Session = Depends(get_session),
):
    return svc.list_orders(session, seller_id_for_user(session, user.id), status, limit, offset)


@router.post("/orders/{order_id}/status", response_model=SellerOrderOut)
def advance(
    order_id: int,
    data: StatusIn,
    user: User = Depends(seller_only),
    session: Session = Depends(get_session),
):
    sid = seller_id_for_user(session, user.id)
    return svc.advance_order(session, sid, user.id, order_id, data.to_status)


@router.get("/products", response_model=list[SellerProductOut])
def list_products(
    q: Annotated[str | None, Query(max_length=100)] = None,
    filter: products_svc.Filter = "all",
    user: User = Depends(seller_only),
    session: Session = Depends(get_session),
):
    return products_svc.list_products(session, seller_id_for_user(session, user.id), q, filter)


@router.patch("/products/{product_id}", response_model=SellerProductOut)
def update_product(
    product_id: int,
    data: ProductPatchIn,
    user: User = Depends(seller_only),
    session: Session = Depends(get_session),
):
    sid = seller_id_for_user(session, user.id)
    return products_svc.update_product(session, sid, product_id, data)
