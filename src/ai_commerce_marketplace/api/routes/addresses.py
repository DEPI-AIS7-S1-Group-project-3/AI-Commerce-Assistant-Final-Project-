from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ai_commerce_marketplace.api.dependencies import get_current_user
from ai_commerce_marketplace.database.models.user import User
from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.schemas.address import AddressIn, AddressOut
from ai_commerce_marketplace.services import addresses as svc

router = APIRouter(prefix="/addresses", tags=["addresses"])


@router.get("", response_model=list[AddressOut])
def list_my_addresses(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return svc.list_addresses(session, user.id)


@router.post("", response_model=AddressOut, status_code=201)
def create(
    data: AddressIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return svc.create_address(session, user.id, data)


@router.put("/{address_id}", response_model=AddressOut)
def update(
    address_id: int,
    data: AddressIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return svc.update_address(session, user.id, address_id, data)


@router.post("/{address_id}/default", response_model=AddressOut)
def make_default(
    address_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    return svc.set_default(session, user.id, address_id)


@router.delete("/{address_id}", status_code=204)
def delete(
    address_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    svc.delete_address(session, user.id, address_id)
    return Response(status_code=204)
