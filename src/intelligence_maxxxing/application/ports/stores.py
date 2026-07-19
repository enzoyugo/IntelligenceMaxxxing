"""Persistence ports.

Constitutional constraint: the event store port is append-only by contract.
It intentionally exposes no update and no delete operation. Constitutional
tests fail if such methods ever appear.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from types import TracebackType

from pydantic import BaseModel, ConfigDict

from intelligence_maxxxing.domain.audit.models import AuditRecord, EngineEvent
from intelligence_maxxxing.domain.common.health import ComponentHealth


class EventStorePort(ABC):
    """Append-only event history. No mutation of recorded events, ever."""

    @abstractmethod
    def append(self, event: EngineEvent) -> None:
        """Append a validated event. Raises on duplicate event_id."""

    @abstractmethod
    def get_by_event_id(self, event_id: str) -> EngineEvent | None: ...

    @abstractmethod
    def list_by_aggregate_id(self, aggregate_id: str) -> Sequence[EngineEvent]: ...

    @abstractmethod
    def list_by_audit_id(self, audit_id: str) -> Sequence[EngineEvent]: ...


class AuditStorePort(ABC):
    """Append-only audit trail."""

    @abstractmethod
    def append(self, record: AuditRecord) -> None: ...

    @abstractmethod
    def get_by_audit_id(self, audit_id: str) -> AuditRecord | None: ...


class IdempotencyRecord(BaseModel):
    """Stored result of a previously accepted idempotent write."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: str
    idempotency_key: str
    payload_hash: str
    observation_id: str
    event_id: str
    audit_id: str


class IdempotencyStorePort(ABC):
    """Maps (scope, idempotency key) to the original accepted result."""

    @abstractmethod
    def get(self, scope: str, idempotency_key: str) -> IdempotencyRecord | None: ...

    @abstractmethod
    def put(self, record: IdempotencyRecord) -> None: ...


class UnitOfWorkPort(ABC):
    """Transactional boundary grouping the stores of a single write path."""

    events: EventStorePort
    audits: AuditStorePort
    idempotency: IdempotencyStorePort

    @abstractmethod
    def __enter__(self) -> "UnitOfWorkPort": ...

    @abstractmethod
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    @abstractmethod
    def commit(self) -> None: ...


class DatabaseHealthPort(ABC):
    """Reports real database health; never fakes a healthy answer."""

    @abstractmethod
    def check(self) -> ComponentHealth: ...
