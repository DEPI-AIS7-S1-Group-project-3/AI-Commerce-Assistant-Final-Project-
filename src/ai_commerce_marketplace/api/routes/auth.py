from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ai_commerce_marketplace.api.dependencies import get_current_user
from ai_commerce_marketplace.database.models.user import User
from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenOut,
    UserOut,
)
from ai_commerce_marketplace.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        role=user.role,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
    )


@router.post("/register", response_model=UserOut, status_code=201)
def register(data: RegisterRequest, session: Session = Depends(get_session)) -> UserOut:
    return _to_out(auth_service.register_customer(session, data))


@router.post("/login", response_model=TokenOut)
def login(data: LoginRequest, session: Session = Depends(get_session)) -> TokenOut:
    return TokenOut(access_token=auth_service.login(session, data.email, data.password))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return _to_out(user)
