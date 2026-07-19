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
from enum import StrEnum
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
    def list_by_aggregate(
        self,
        tenant_id: str,
        owner_id: str,
        application_id: str,
        aggregate_id: str,
    ) -> Sequence[EngineEvent]:
        """Aggregate history within ONE (tenant, owner, application) scope.

        Aggregate lookups never cross an application: the same aggregate_id in
        another application is a different stream and is not returned here.
        """

    @abstractmethod
    def list_by_audit(
        self,
        tenant_id: str,
        owner_id: str,
        application_id: str,
        audit_id: str,
    ) -> Sequence[EngineEvent]:
        """Events of an audit, scoped by tenant + owner + application.

        An application can only see events of audits produced under its own
        (tenant, owner, application); anything else behaves as not found.
        """

    @abstractmethod
    def list_by_owner(
        self, owner_id: str, application_id: str | None = None
    ) -> Sequence[EngineEvent]: ...

    @abstractmethod
    def stream_from_position(self, position: int, limit: int) -> Sequence[EngineEvent]:
        """Global ordered stream (trusted engine services only, e.g. projector)."""

    @abstractmethod
    def stream_for_stream_key(
        self,
        tenant_id: str,
        owner_id: str,
        application_id: str,
        from_position: int = 0,
    ) -> Sequence[EngineEvent]:
        """One (tenant, owner, application) integrity stream in global order."""

    @abstractmethod
    def list_stream_keys(self) -> Sequence[tuple[str, str, str]]:
        """All distinct (tenant_id, owner_id, application_id) streams."""

    @abstractmethod
    def get_latest_aggregate_version(
        self,
        tenant_id: str,
        owner_id: str,
        application_id: str,
        aggregate_type: str,
        aggregate_id: str,
    ) -> int | None:
        """Latest recorded version for optimistic concurrency, or None.

        Scoped by (tenant, owner, application): concurrency and version
        assignment for an aggregate never observe another application's stream.
        """


class AuditStorePort(ABC):
    """Append-only audit trail. Reads are scoped by tenant + owner + application."""

    @abstractmethod
    def append(self, record: AuditRecord) -> None: ...

    @abstractmethod
    def get_by_audit_id(
        self,
        tenant_id: str,
        owner_id: str,
        application_id: str,
        audit_id: str,
    ) -> AuditRecord | None:
        """Retrieve an audit only if it belongs to the given scope.

        A caller cannot read an audit of another application (even under the
        same owner) or another tenant; those behave exactly like a missing id
        (404, not 403) to avoid existence leaks.
        """


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


GLOBAL_SCOPE = "ALL"


class ProjectionCheckpoint(BaseModel):
    """Checkpoint of a projection (mutable DERIVED state; documented
    exception to append-only).

    Scoping model (Stage 1.1 §9): the `accepted_observations` projector runs
    GLOBALLY across every owner/application while keeping each projected ROW
    owner/application-scoped. Its checkpoint is therefore a single global row
    with ``owner_scope == application_scope == "ALL"``. There is intentionally
    no per-application checkpoint interface; a lookup by
    (projection_name, projection_version) is unambiguous by construction.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    projection_name: str
    projection_version: str
    owner_scope: str = GLOBAL_SCOPE
    application_scope: str = GLOBAL_SCOPE
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
        """All LIVE rows in deterministic order (verification/checksum only)."""

    @abstractmethod
    def delete_all_observations(self) -> int:
        """Rebuild support: the projection is derived state, never the ledger."""

    # ---- shadow / staging (non-destructive verify + atomic promote) -------

    @abstractmethod
    def upsert_shadow_observation(self, row: ProjectedObservation) -> None:
        """Idempotent apply into the SHADOW table (never touches live)."""

    @abstractmethod
    def list_all_shadow_observations(self) -> Sequence[ProjectedObservation]:
        """All SHADOW rows in deterministic order (checksum/compare only)."""

    @abstractmethod
    def delete_all_shadow_observations(self) -> int:
        """Clear the shadow/staging table before a shadow build."""

    @abstractmethod
    def promote_shadow_observations(self) -> int:
        """Atomically replace live rows with the shadow set (same transaction).

        Live is emptied and refilled from shadow, then shadow is cleared. The
        whole swap commits or rolls back as one unit.
        """

    @abstractmethod
    def get_checkpoint(
        self, projection_name: str, projection_version: str
    ) -> ProjectionCheckpoint | None: ...

    @abstractmethod
    def save_checkpoint(self, checkpoint: ProjectionCheckpoint) -> None: ...

    @abstractmethod
    def delete_checkpoint(self, projection_name: str, projection_version: str) -> None: ...


class StreamStatus(StrEnum):
    ACTIVE = "ACTIVE"
    QUARANTINED = "QUARANTINED"
    REBUILD_REQUIRED = "REBUILD_REQUIRED"


class StreamHead(BaseModel):
    """Snapshot of one integrity stream head (read model)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str
    owner_id: str
    application_id: str
    last_global_position: int
    last_event_id: str | None
    current_event_hash: str | None
    stream_version: int
    status: str
    quarantine_reason: str | None = None
    broken_event_id: str | None = None
    quarantined_at: datetime | None = None
    quarantine_audit_id: str | None = None
    updated_at: datetime


class IntegrityStreamCheckpoint(BaseModel):
    """Last reliably verified point of one integrity stream."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str
    owner_id: str
    application_id: str
    last_verified_global_position: int
    last_verified_event_id: str | None
    last_verified_hash: str | None
    verified_at: datetime
    status: str


class IntegrityStorePort(ABC):
    """Stream heads and integrity checkpoints.

    Stream heads and integrity checkpoints are engine-managed control state
    (not ledger evidence): the runtime may update them through these governed
    methods, but never rewrites events or audits, and never releases a
    quarantine implicitly.
    """

    @abstractmethod
    def get_stream_head(
        self, tenant_id: str, owner_id: str, application_id: str
    ) -> StreamHead | None: ...

    @abstractmethod
    def list_stream_heads(self) -> Sequence[StreamHead]: ...

    @abstractmethod
    def quarantine_stream(
        self,
        tenant_id: str,
        owner_id: str,
        application_id: str,
        *,
        reason: str,
        broken_event_id: str,
        audit_id: str,
        detected_at: datetime,
    ) -> None:
        """Set the stream status to QUARANTINED (kill-switch)."""

    @abstractmethod
    def release_stream(self, tenant_id: str, owner_id: str, application_id: str) -> None:
        """Return a QUARANTINED stream to ACTIVE (governed admin path only)."""

    @abstractmethod
    def get_integrity_checkpoint(
        self, tenant_id: str, owner_id: str, application_id: str
    ) -> IntegrityStreamCheckpoint | None: ...

    @abstractmethod
    def save_integrity_checkpoint(self, checkpoint: IntegrityStreamCheckpoint) -> None: ...


class UnitOfWorkPort(ABC):
    """Transactional boundary grouping the stores of a single write path."""

    events: EventStorePort
    audits: AuditStorePort
    idempotency: IdempotencyStorePort
    identity: IdentityStorePort
    projections: ProjectionStorePort
    integrity: IntegrityStorePort

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
