from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ai_commerce_marketplace.api.dependencies import get_current_user
from ai_commerce_marketplace.database.models.user import User
from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.schemas.order import CheckoutIn, CheckoutOut
from ai_commerce_marketplace.services import checkout as svc

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=CheckoutOut, status_code=201)
def create_order(
    data: CheckoutIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    # customer id comes from the token; only address_id and payment_method come from the body
    return svc.checkout(session, user.id, data.address_id, data.payment_method)
