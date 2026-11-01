from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ai_commerce_marketplace.api.dependencies import get_current_user
from ai_commerce_marketplace.database.models.user import User
from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.schemas.order import (
    CheckoutIn,
    CheckoutOut,
    OrderDetailOut,
    OrderOut,
    ReturnIn,
    ReturnOut,
)
from ai_commerce_marketplace.services import checkout as svc
from ai_commerce_marketplace.services import order_actions as actions_svc
from ai_commerce_marketplace.services import orders as orders_svc

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=CheckoutOut, status_code=201)
def create_order(
    data: CheckoutIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    # customer id comes from the token; only address_id and payment_method come from the body
    return svc.checkout(session, user.id, data.address_id, data.payment_method)


@router.get("", response_model=list[OrderOut])
def list_my_orders(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return orders_svc.list_orders(session, user.id)


@router.get("/{order_id}", response_model=OrderDetailOut)
def get_my_order(
    order_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return orders_svc.get_order(session, user.id, order_id)


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel(
    order_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    actions_svc.cancel_order(session, user.id, order_id)
    return orders_svc.get_order(session, user.id, order_id)


@router.post("/{order_id}/items/{item_id}/return", response_model=ReturnOut, status_code=201)
def return_item(
    order_id: int,
    item_id: int,
    data: ReturnIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    ret = actions_svc.request_return(
        session, user.id, order_id, item_id, data.reason_code, data.reason_text
    )
    return ReturnOut(
        id=ret.id,
        order_item_id=ret.order_item_id,
        qty=ret.qty,
        reason_code=ret.reason_code,
        status=ret.status,
    )
