"""Typed SDK errors."""

from typing import Any


class EngineClientError(Exception):
    """Base error for the IntelligenceMaxxxing client."""


class EngineUnavailableError(EngineClientError):
    """The Engine could not be reached (network error or timeout)."""


class EngineAPIError(EngineClientError):
    """The Engine returned a typed error envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.request_id = request_id


class EngineValidationError(EngineAPIError):
    """The request failed validation (HTTP 422)."""


class EngineConflictError(EngineAPIError):
    """Idempotency key reused with a different payload (HTTP 409)."""


class EngineNotFoundError(EngineAPIError):
    """The requested resource does not exist (HTTP 404)."""
