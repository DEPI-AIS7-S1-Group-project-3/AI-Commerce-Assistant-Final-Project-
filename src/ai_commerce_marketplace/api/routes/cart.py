from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ai_commerce_marketplace.api.dependencies import get_current_user
from ai_commerce_marketplace.database.models.user import User
from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.schemas.cart import CartItemIn, CartOut, CartQtyIn
from ai_commerce_marketplace.services import cart as svc

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("", response_model=CartOut)
def get_cart(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return svc.view_cart(session, user.id)


@router.post("/items", response_model=CartOut)
def add(
    data: CartItemIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return svc.add_item(session, user.id, data.product_id, data.qty)


@router.put("/items/{product_id}", response_model=CartOut)
def set_quantity(
    product_id: int,
    data: CartQtyIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return svc.set_qty(session, user.id, product_id, data.qty)


@router.delete("/items/{product_id}", response_model=CartOut)
def remove(
    product_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return svc.remove_item(session, user.id, product_id)


@router.delete("", response_model=CartOut)
def clear(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return svc.clear_cart(session, user.id)
