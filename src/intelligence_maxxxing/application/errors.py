"""Typed application errors surfaced through the public error contract."""


class ApplicationError(Exception):
    """Base class for expected, typed application failures."""

    code = "APPLICATION_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class IdempotencyConflictError(ApplicationError):
    """Same idempotency key was reused with a different payload."""

    code = "IDEMPOTENCY_CONFLICT"


class AuditNotFoundError(ApplicationError):
    """The requested audit record does not exist."""

    code = "AUDIT_NOT_FOUND"
