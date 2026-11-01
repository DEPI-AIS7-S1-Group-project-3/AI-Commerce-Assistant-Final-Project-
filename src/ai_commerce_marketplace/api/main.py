import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ai_commerce_marketplace.api.routes import addresses, auth, health
from ai_commerce_marketplace.core.config import settings
from ai_commerce_marketplace.core.exceptions import AppError


def _error(
    request: Request,
    status: int,
    code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    """Build the unified error response: {code, message, details}."""
    return JSONResponse(
        status_code=status,
        content={"code": code, "message": message, "details": details},
        headers={"X-Request-ID": request.state.request_id},
    )


def create_app() -> FastAPI:
    app = FastAPI(title="AI Commerce Marketplace", version="0.1.0")

    # CORS: only the configured frontend origins, never "*".
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        # Reuse the caller's request ID if present, otherwise generate one.
        request.state.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        try:
            response = await call_next(request)
        except Exception:
            # Never leak stack traces or internal details to the client.
            return _error(request, 500, "internal_error", "An unexpected error occurred")
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return _error(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return _error(request, 404, "not_found", "Route not found")
        return _error(request, exc.status_code, "http_error", "Invalid request")

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        # ctx may hold the raw ValueError, which is not JSON serializable.
        details = [
            {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()
        ]
        return _error(request, 422, "validation_error", "Invalid data", jsonable_encoder(details))

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(addresses.router)
    return app


app = create_app()
