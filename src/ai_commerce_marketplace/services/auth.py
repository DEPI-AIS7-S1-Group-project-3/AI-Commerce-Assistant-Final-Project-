from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.enums import Role
from ai_commerce_marketplace.core.exceptions import (
    AppError,
    ConflictError,
    UnauthorizedError,
)
from ai_commerce_marketplace.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from ai_commerce_marketplace.database.models.user import User
from ai_commerce_marketplace.schemas.auth import RegisterRequest

# Hash used to keep login timing similar when the email does not exist.
_DUMMY_HASH = hash_password("not-a-real-password-1")


def _by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(func.lower(User.email) == email.lower()))


def register_customer(session: Session, data: RegisterRequest) -> User:
    if data.role != Role.CUSTOMER:
        raise AppError("Only customer accounts can self-register", code="role_not_allowed")
    if _by_email(session, data.email) is not None:
        raise ConflictError("Email is already registered", code="email_taken")
    user = User(
        role=Role.CUSTOMER,
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        password_hash=hash_password(data.password),
    )
    session.add(user)
    session.commit()
    return user


def login(session: Session, email: str, password: str) -> str:
    user = _by_email(session, email)
    if user is None:
        verify_password(_DUMMY_HASH, password)  # equalize timing
        raise UnauthorizedError("Invalid email or password", code="invalid_credentials")
    if not verify_password(user.password_hash, password) or not user.is_active:
        raise UnauthorizedError("Invalid email or password", code="invalid_credentials")
    return create_access_token(user.id, user.role)
