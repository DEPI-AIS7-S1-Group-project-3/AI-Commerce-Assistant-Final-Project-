from collections.abc import Callable

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.exceptions import ForbiddenError, UnauthorizedError
from ai_commerce_marketplace.core.security import decode_access_token
from ai_commerce_marketplace.database.models.user import User
from ai_commerce_marketplace.database.session import get_session

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> User:
    if creds is None:
        raise UnauthorizedError()
    try:
        payload = decode_access_token(creds.credentials)
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise UnauthorizedError("Invalid or expired token", code="invalid_token") from None
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid or expired token", code="invalid_token")
    return user


def require_role(role: str) -> Callable[[User], User]:
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role != role:
            raise ForbiddenError()
        return user

    return checker
