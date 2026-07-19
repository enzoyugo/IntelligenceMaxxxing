"""Persistence ports.

Constitutional constraint: the event store and audit store ports are
append-only by contract. They intentionally expose no update and no delete
operation; constitutional tests fail if such methods ever appear.

Stage 1: every read is scoped by owner/application. Repository queries without
scope do not exist on the ports (closed by design, not by convention).
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from types import TracebackType

from pydantic import BaseModel, ConfigDict, Field

from intelligence_maxxxing.domain.audit.models import AuditRecord, EngineEvent
from intelligence_maxxxing.domain.common.health import ComponentHealth, HealthSnapshot
from intelligence_maxxxing.domain.identity import (
    ApplicationIdentity,
    CredentialStatus,
    IdentityStatus,
    TenantIdentity,
    UserIdentity,
)


class EventStorePort(ABC):
    """Append-only event history. No mutation of recorded events, ever.

    The store validates every payload against the event catalog and maintains
    the per-(owner, application) integrity hash chain at append time.
    """

    @abstractmethod
    def append_one(self, event: EngineEvent) -> EngineEvent:
        """Append a validated event; returns it with hash chain fields set."""

    @abstractmethod
    def append_batch(self, events: Sequence[EngineEvent]) -> Sequence[EngineEvent]:
        """Append several events atomically, in deterministic input order."""

    @abstractmethod
    def get_by_event_id(self, event_id: str) -> EngineEvent | None: ...

    @abstractmethod
    def list_by_aggregate(self, owner_id: str, aggregate_id: str) -> Sequence[EngineEvent]: ...

    @abstractmethod
    def list_by_audit(self, owner_id: str, audit_id: str) -> Sequence[EngineEvent]: ...

    @abstractmethod
    def list_by_owner(
        self, owner_id: str, application_id: str | None = None
    ) -> Sequence[EngineEvent]: ...

    @abstractmethod
    def stream_from_position(self, position: int, limit: int) -> Sequence[EngineEvent]:
        """Global ordered stream (trusted engine services only, e.g. projector)."""

    @abstractmethod
    def stream_for_stream_key(
        self, owner_id: str, application_id: str, from_position: int = 0
    ) -> Sequence[EngineEvent]:
        """One (owner, application) integrity stream in global order."""

    @abstractmethod
    def list_stream_keys(self) -> Sequence[tuple[str, str]]:
        """All distinct (owner_id, application_id) streams."""

    @abstractmethod
    def get_latest_aggregate_version(self, aggregate_type: str, aggregate_id: str) -> int | None:
        """Latest recorded version for optimistic concurrency, or None."""


class AuditStorePort(ABC):
    """Append-only audit trail. Reads are owner-scoped."""

    @abstractmethod
    def append(self, record: AuditRecord) -> None: ...

    @abstractmethod
    def get_by_audit_id(self, owner_id: str, audit_id: str) -> AuditRecord | None: ...


class IdempotencyRecord(BaseModel):
    """Stored result of a previously accepted idempotent write.

    Effective scope (Stage 1): tenant + owner + application + action + key.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str
    owner_id: str
    application_id: str
    actor_id: str
    action: str
    idempotency_key: str
    payload_hash: str
    observation_id: str
    event_id: str
    audit_id: str


class IdempotencyStorePort(ABC):
    """Maps the composite idempotency scope to the original accepted result."""

    @abstractmethod
    def get(
        self, application_id: str, owner_id: str, action: str, idempotency_key: str
    ) -> IdempotencyRecord | None: ...

    @abstractmethod
    def put(self, record: IdempotencyRecord) -> None: ...


class CredentialRecord(BaseModel):
    """An application API credential. The secret exists only as a hash."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    credential_id: str
    application_id: str
    secret_hash: str
    status: CredentialStatus
    created_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    audit_id: str


class IdentityStorePort(ABC):
    """Identity registry: tenants, users, applications, credentials, scopes.

    Administrative state (mutable by governed use cases only); every change is
    also recorded as an append-only event + audit.
    """

    @abstractmethod
    def add_tenant(self, tenant: TenantIdentity) -> None: ...

    @abstractmethod
    def get_tenant(self, tenant_id: str) -> TenantIdentity | None: ...

    @abstractmethod
    def list_tenants(self) -> Sequence[TenantIdentity]: ...

    @abstractmethod
    def add_user(self, user: UserIdentity) -> None: ...

    @abstractmethod
    def get_user(self, user_id: str) -> UserIdentity | None: ...

    @abstractmethod
    def list_users(self) -> Sequence[UserIdentity]: ...

    @abstractmethod
    def add_application(self, application: ApplicationIdentity, scopes: Sequence[str]) -> None: ...

    @abstractmethod
    def get_application(self, application_id: str) -> ApplicationIdentity | None: ...

    @abstractmethod
    def list_applications(self) -> Sequence[ApplicationIdentity]: ...

    @abstractmethod
    def get_application_scopes(self, application_id: str) -> Sequence[str]: ...

    @abstractmethod
    def set_application_scopes(self, application_id: str, scopes: Sequence[str]) -> None: ...

    @abstractmethod
    def set_application_status(
        self, application_id: str, status: IdentityStatus, disabled_at: datetime | None
    ) -> None: ...

    @abstractmethod
    def add_credential(self, credential: CredentialRecord) -> None: ...

    @abstractmethod
    def get_credential(self, credential_id: str) -> CredentialRecord | None: ...

    @abstractmethod
    def list_credentials(self, application_id: str) -> Sequence[CredentialRecord]: ...

    @abstractmethod
    def set_credential_status(
        self, credential_id: str, status: CredentialStatus, revoked_at: datetime | None
    ) -> None: ...

    @abstractmethod
    def touch_credential(self, credential_id: str, last_used_at: datetime) -> None: ...


class ProjectedObservation(BaseModel):
    """One row of the accepted_observations projection (derived state)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str
    global_position: int
    event_id: str
    tenant_id: str
    owner_id: str
    application_id: str
    domain_pack: str
    schema_version: str
    subject: str
    statement: str
    knowledge_class: str
    unknown_reason: str | None = None
    observed_by: str
    context: dict[str, object] = Field(default_factory=dict)
    source_ids: tuple[str, ...] = ()
    metadata: dict[str, object] = Field(default_factory=dict)
    occurred_at: datetime | None = None
    created_at: datetime
    audit_id: str


class ObservationListFilters(BaseModel):
    """Deterministic, owner-scoped listing filters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    domain_pack: str | None = None
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None
    after_position: int | None = None  # cursor: global_position of last seen row
    limit: int = Field(default=50, ge=1, le=500)


class ProjectionCheckpoint(BaseModel):
    """Checkpoint of a projection (mutable DERIVED state; documented
    exception to append-only)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    projection_name: str
    projection_version: str
    owner_scope: str
    application_scope: str
    last_global_position: int = 0
    last_event_id: str | None = None
    updated_at: datetime
    status: str
    checksum: str | None = None


class ProjectionStorePort(ABC):
    """accepted_observations projection + checkpoints. Derived, rebuildable."""

    @abstractmethod
    def upsert_observation(self, row: ProjectedObservation) -> None:
        """Idempotent apply: replay of the same event yields the same row."""

    @abstractmethod
    def get_observation(
        self, owner_id: str, application_id: str, observation_id: str
    ) -> ProjectedObservation | None: ...

    @abstractmethod
    def list_observations(
        self, owner_id: str, application_id: str, filters: ObservationListFilters
    ) -> Sequence[ProjectedObservation]: ...

    @abstractmethod
    def list_all_observations(self) -> Sequence[ProjectedObservation]:
        """All rows in deterministic order (verification/checksum only)."""

    @abstractmethod
    def delete_all_observations(self) -> int:
        """Rebuild support: the projection is derived state, never the ledger."""

    @abstractmethod
    def get_checkpoint(
        self, projection_name: str, projection_version: str
    ) -> ProjectionCheckpoint | None: ...

    @abstractmethod
    def save_checkpoint(self, checkpoint: ProjectionCheckpoint) -> None: ...

    @abstractmethod
    def delete_checkpoint(self, projection_name: str, projection_version: str) -> None: ...


class UnitOfWorkPort(ABC):
    """Transactional boundary grouping the stores of a single write path."""

    events: EventStorePort
    audits: AuditStorePort
    idempotency: IdempotencyStorePort
    identity: IdentityStorePort
    projections: ProjectionStorePort

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


class HealthSnapshotProviderPort(ABC):
    """Produces measured HealthSnapshots for audits.

    Use cases MUST obtain audit health state from this provider; they can not
    construct a dict claiming health they did not measure.
    """

    @abstractmethod
    def capture(self) -> HealthSnapshot: ...


class RateLimitHookPort(ABC):
    """Rate limiting hook (Stage 1: contract only, default implementation is
    a no-op). A future stage can plug real limits without API changes."""

    @abstractmethod
    def check(self, application_id: str, action: str) -> None:
        """Raise a typed error to reject the request; return to allow it."""


class IntegrityViolationHookPort(ABC):
    """Kill-switch hook invoked when the integrity chain is broken."""

    @abstractmethod
    def on_violation(self, owner_id: str, application_id: str, broken_event_id: str) -> None: ...
