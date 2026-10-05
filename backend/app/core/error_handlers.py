"""
Centralized error handling.

API_SPEC.md mandates every error response use:
    { "error": { "code": "STRING_CODE", "message": "...", "details": {} } }
This is the ONLY place in the codebase that builds that envelope.
"""
import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError, RateLimitedError

logger = logging.getLogger("keymood.errors")


def _envelope(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        headers = {}
        if isinstance(exc, RateLimitedError):
            headers["Retry-After"] = str(exc.retry_after_seconds)
        if exc.http_status >= 500:
            logger.error(
                "unhandled_app_error",
                extra={"path": request.url.path, "error_code": exc.error_code},
                exc_info=exc,
            )
        return JSONResponse(
            status_code=exc.http_status,
            content=_envelope(exc.error_code, exc.message, exc.details),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                "VALIDATION_ERROR",
                "Request payload failed validation.",
                {"errors": exc.errors()},
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        incident_id = str(uuid.uuid4())
        logger.error(
            "unexpected_error",
            extra={"path": request.url.path, "incident_id": incident_id},
            exc_info=exc,
        )
        # Generic message to the client per API_SPEC.md 500 INTERNAL_ERROR —
        # the real detail is only in error_logs/server logs, never leaked to the client.
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope(
                "INTERNAL_ERROR",
                "An unexpected error occurred.",
                {"incident_id": incident_id},
            ),
        )
