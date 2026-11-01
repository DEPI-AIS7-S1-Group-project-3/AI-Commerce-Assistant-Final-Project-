from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.exceptions import NotFoundError
from ai_commerce_marketplace.database.models.user import Address
from ai_commerce_marketplace.schemas.address import AddressIn


def _get_owned(session: Session, user_id: int, address_id: int) -> Address:
    stmt = select(Address).where(Address.id == address_id, Address.user_id == user_id)
    addr = session.scalar(stmt)
    if addr is None:
        raise NotFoundError("Address not found", code="address_not_found")
    return addr


def _clear_default(session: Session, user_id: int) -> None:
    stmt = (
        update(Address)
        .where(Address.user_id == user_id, Address.is_default)
        .values(is_default=False)
    )
    session.execute(stmt)


def list_addresses(session: Session, user_id: int) -> list[Address]:
    stmt = (
        select(Address)
        .where(Address.user_id == user_id)
        .order_by(Address.is_default.desc(), Address.id)
    )
    return list(session.scalars(stmt))


def create_address(session: Session, user_id: int, data: AddressIn) -> Address:
    has_any = session.scalar(select(Address.id).where(Address.user_id == user_id).limit(1))
    make_default = data.is_default or has_any is None
    if make_default:
        _clear_default(session, user_id)
    fields = data.model_dump(exclude={"is_default"})
    addr = Address(**fields, user_id=user_id, is_default=make_default)
    session.add(addr)
    session.commit()
    return addr


def update_address(session: Session, user_id: int, address_id: int, data: AddressIn) -> Address:
    addr = _get_owned(session, user_id, address_id)
    if data.is_default and not addr.is_default:
        _clear_default(session, user_id)
        addr.is_default = True
    # An existing default cannot be unset by an update; set another one as default instead.
    for field, value in data.model_dump(exclude={"is_default"}).items():
        setattr(addr, field, value)
    session.commit()
    return addr


def set_default(session: Session, user_id: int, address_id: int) -> Address:
    addr = _get_owned(session, user_id, address_id)
    if not addr.is_default:
        _clear_default(session, user_id)
        addr.is_default = True
        session.commit()
    return addr


def delete_address(session: Session, user_id: int, address_id: int) -> None:
    addr = _get_owned(session, user_id, address_id)
    was_default = addr.is_default
    session.delete(addr)
    session.flush()
    if was_default:
        newest = session.scalar(
            select(Address).where(Address.user_id == user_id).order_by(Address.id.desc()).limit(1)
        )
        if newest is not None:
            newest.is_default = True
    session.commit()
