from typing import Any


class AppError(Exception):
    """Base class for all expected application errors."""

    status_code: int = 400
    code: str = "app_error"
    message: str = "An error occurred"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.code = code or self.code
        self.details = details


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "The requested item was not found"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    message = "You must log in first"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    message = "You are not allowed to perform this action"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "Data conflict"
