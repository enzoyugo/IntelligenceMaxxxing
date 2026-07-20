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
    """The requested audit record does not exist (within the caller's scope)."""

    code = "AUDIT_NOT_FOUND"


class ObservationNotFoundError(ApplicationError):
    """The requested observation does not exist (within the caller's scope)."""

    code = "OBSERVATION_NOT_FOUND"


class AuthenticationError(ApplicationError):
    """The request could not be authenticated (missing/invalid/revoked/expired
    credential, or disabled application). Maps to HTTP 401."""

    code = "AUTHENTICATION_REQUIRED"


class PermissionDeniedError(ApplicationError):
    """Authenticated, but the application lacks the required scope or tried to
    access another owner's data. Maps to HTTP 403."""

    code = "PERMISSION_DENIED"


class ConcurrencyConflictError(ApplicationError):
    """Optimistic concurrency violation on an aggregate version."""

    code = "CONCURRENCY_CONFLICT"


class IdempotencyRaceDetected(ApplicationError):
    """Internal signal: a concurrent request with the same idempotency scope
    committed first. Resolved deterministically by the use case; never
    surfaced to clients."""

    code = "IDEMPOTENCY_RACE"


class UnregisteredEventTypeError(ApplicationError):
    """Event type + schema version is not declared in the event catalog."""

    code = "UNREGISTERED_EVENT_TYPE"


class EventPayloadInvalidError(ApplicationError):
    """Event payload does not match the catalog schema for its type/version."""

    code = "EVENT_PAYLOAD_INVALID"


class IntegrityViolationError(ApplicationError):
    """The event integrity chain is broken: alteration or corruption detected."""

    code = "INTEGRITY_VIOLATION"


class IdentityError(ApplicationError):
    """Identity administration failed (unknown application, duplicate, ...)."""

    code = "IDENTITY_ERROR"


class MigrationBlockedError(ApplicationError):
    """A destructive migration was blocked by the safety policy."""

    code = "MIGRATION_BLOCKED"


class UnknownProjectionEventError(ApplicationError):
    """The projector met an event type it does not know how to apply.

    Policy: STOP (fail closed). The checkpoint is marked QUARANTINED and the
    projection does not silently skip history.
    """

    code = "UNKNOWN_PROJECTION_EVENT"


class StreamQuarantinedError(ApplicationError):
    """The (tenant, owner, application) integrity stream is QUARANTINED after a
    detected chain break. All new writes to it are rejected until an operator
    releases it through the governed admin CLI. Maps to HTTP 409 (a durable
    state conflict, not a transient outage)."""

    code = "STREAM_QUARANTINED"


class StreamNotFoundError(ApplicationError):
    """No integrity stream head exists for the requested scope."""

    code = "STREAM_NOT_FOUND"


class StreamReleaseBlockedError(ApplicationError):
    """A quarantined stream cannot be released: full verification still fails
    (or the required authorization/repair was not provided)."""

    code = "STREAM_RELEASE_BLOCKED"


class HypothesisNotFoundError(ApplicationError):
    """The requested hypothesis does not exist (within the caller's scope)."""

    code = "HYPOTHESIS_NOT_FOUND"


class ExperimentNotFoundError(ApplicationError):
    """The requested experiment does not exist (within the caller's scope)."""

    code = "EXPERIMENT_NOT_FOUND"


class HypothesisStateError(ApplicationError):
    """The hypothesis is not in a valid state for the requested operation."""

    code = "HYPOTHESIS_STATE_ERROR"


class UnknownFormulaError(ApplicationError):
    """Requested wellbeing formula_id is not registered."""

    code = "UNKNOWN_FORMULA"
