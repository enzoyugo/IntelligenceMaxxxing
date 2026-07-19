"""ORM table definitions (internal only; never exposed as public contracts).

Designed for PostgreSQL. SQLite is used only in tests.

Append-only guarantees for `engine_events` and `audit_records` are enforced at
three levels: Python ports (no mutation methods), SQL triggers (reject
UPDATE/DELETE/TRUNCATE) and PostgreSQL role grants (runtime role has no
UPDATE/DELETE/TRUNCATE privilege). `projection_checkpoints` and identity
tables are mutable derived/administrative state - a documented exception.
"""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# BigInteger global position with SQLite fallback (INTEGER PRIMARY KEY = rowid).
_GlobalPosition = BigInteger().with_variant(Integer(), "sqlite")


class Base(DeclarativeBase):
    pass


class EngineEventRow(Base):
    """Append-only event log. Rows are inserted, never updated or deleted."""

    __tablename__ = "engine_events"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_engine_events_event_id"),
        UniqueConstraint(
            "application_id",
            "idempotency_scope",
            "idempotency_key",
            name="uq_engine_events_idempotency_scope_key",
        ),
        UniqueConstraint(
            "aggregate_type",
            "aggregate_id",
            "aggregate_version",
            name="uq_engine_events_aggregate_version",
        ),
    )

    global_position: Mapped[int] = mapped_column(
        _GlobalPosition, primary_key=True, autoincrement=True
    )
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    domain_pack: Mapped[str] = mapped_column(String(64), nullable=False, default="core")
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    audit_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_scope: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # Integrity chain (per owner/application stream). Nullable only for
    # pre-Stage-1 legacy events, which predate the chain.
    previous_event_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class AuditRecordRow(Base):
    """Append-only audit trail."""

    __tablename__ = "audit_records"

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    api_version: Mapped[str] = mapped_column(String(16), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    domain_pack: Mapped[str] = mapped_column(String(64), nullable=False, default="core")
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    input_object_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    output_object_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    event_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    health_state: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class IdempotencyKeyRow(Base):
    """Idempotency ledger mapping a composite scope to the original result.

    Effective scope: (tenant, owner, application, action, idempotency key).
    Two different applications can reuse the same key without collision.
    """

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "owner_id",
            "action",
            "idempotency_key",
            name="uq_idempotency_scope_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    observation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_id: Mapped[str] = mapped_column(String(64), nullable=False)


class TenantRow(Base):
    """Logical tenants. Initially one: the Constitutional Owner's instance."""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    audit_id: Mapped[str] = mapped_column(String(64), nullable=False)


class UserRow(Base):
    """Human users (owners of data)."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    audit_id: Mapped[str] = mapped_column(String(64), nullable=False)


class ApplicationRow(Base):
    """Registered external applications. Scopes live here, not on tokens:
    a credential can never elevate its own scopes."""

    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    audit_id: Mapped[str] = mapped_column(String(64), nullable=False)


class ApplicationCredentialRow(Base):
    """API credentials. Secrets are stored ONLY as SHA-256 hashes."""

    __tablename__ = "application_credentials"

    credential_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    audit_id: Mapped[str] = mapped_column(String(64), nullable=False)


class AcceptedObservationRow(Base):
    """Projection: queryable state of accepted observations.

    Derived exclusively from engine_events. Disposable and rebuildable; it is
    never the primary source of truth.
    """

    __tablename__ = "accepted_observations"

    observation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    global_position: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    domain_pack: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    statement: Mapped[str] = mapped_column(String(4000), nullable=False)
    knowledge_class: Mapped[str] = mapped_column(String(64), nullable=False)
    unknown_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    observed_by: Mapped[str] = mapped_column(String(256), nullable=False)
    context: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    source_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    meta: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    audit_id: Mapped[str] = mapped_column(String(64), nullable=False)


class ProjectionCheckpointRow(Base):
    """Projection checkpoints: mutable DERIVED state (documented exception to
    append-only; rebuild history itself is recorded as events/audits)."""

    __tablename__ = "projection_checkpoints"
    __table_args__ = (
        UniqueConstraint(
            "projection_name",
            "projection_version",
            "owner_scope",
            "application_scope",
            name="uq_projection_checkpoint_scope",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    projection_name: Mapped[str] = mapped_column(String(128), nullable=False)
    projection_version: Mapped[str] = mapped_column(String(16), nullable=False)
    # 'ALL' is the modeled, documented marker for a projector that runs across
    # every owner/application while keeping each projected row owner-scoped.
    owner_scope: Mapped[str] = mapped_column(String(64), nullable=False)
    application_scope: Mapped[str] = mapped_column(String(64), nullable=False)
    last_global_position: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
