"""Typed error handling. No stack traces or secrets ever reach the client."""

from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from intelligence_maxxxing.api.envelope import build_meta, error_envelope
from intelligence_maxxxing.application.errors import (
    ApplicationError,
    AuditNotFoundError,
    AuthenticationError,
    ExperimentNotFoundError,
    HypothesisNotFoundError,
    HypothesisStateError,
    IdempotencyConflictError,
    ObservationNotFoundError,
    PermissionDeniedError,
    StreamQuarantinedError,
)
from intelligence_maxxxing.observability import get_logger

logger = get_logger("intelligence_maxxxing.api.errors")

_STATUS_BY_ERROR: dict[type[ApplicationError], int] = {
    IdempotencyConflictError: status.HTTP_409_CONFLICT,
    AuditNotFoundError: status.HTTP_404_NOT_FOUND,
    ObservationNotFoundError: status.HTTP_404_NOT_FOUND,
    HypothesisNotFoundError: status.HTTP_404_NOT_FOUND,
    ExperimentNotFoundError: status.HTTP_404_NOT_FOUND,
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    PermissionDeniedError: status.HTTP_403_FORBIDDEN,
    HypothesisStateError: status.HTTP_409_CONFLICT,
    # A quarantined stream is a durable state conflict (needs a governed
    # release), not a transient outage: 409, consistent across the API.
    StreamQuarantinedError: status.HTTP_409_CONFLICT,
}


def _meta_for(request: Request) -> Any:
    request_id = getattr(request.state, "request_id", "req_unknown")
    engine_version = request.app.state.settings.engine_version
    return build_meta(request_id=request_id, engine_version=engine_version)


def _sanitize_validation_errors(errors: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized = []
    for error in errors:
        sanitized.append(
            {
                "loc": [str(part) for part in error.get("loc", [])],
                "msg": str(error.get("msg", "invalid input")),
                "type": str(error.get("type", "value_error")),
            }
        )
    return sanitized


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        envelope = error_envelope(
            code="VALIDATION_ERROR",
            message="request validation failed",
            meta=_meta_for(request),
            details={"errors": _sanitize_validation_errors(exc.errors())},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=envelope.model_dump(),
        )

    @app.exception_handler(ApplicationError)
    async def application_error_handler(request: Request, exc: ApplicationError) -> JSONResponse:
        status_code = _STATUS_BY_ERROR.get(type(exc), status.HTTP_400_BAD_REQUEST)
        envelope = error_envelope(code=exc.code, message=exc.message, meta=_meta_for(request))
        headers = (
            {"WWW-Authenticate": "Bearer"} if status_code == status.HTTP_401_UNAUTHORIZED else None
        )
        return JSONResponse(status_code=status_code, content=envelope.model_dump(), headers=headers)

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Full detail goes to structured logs; the client gets a typed error only.
        logger.error(
            "unhandled error",
            exc_info=exc,
            extra={"request_id": getattr(request.state, "request_id", None)},
        )
        envelope = error_envelope(
            code="INTERNAL_ERROR",
            message="an internal error occurred",
            meta=_meta_for(request),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=envelope.model_dump(),
        )
