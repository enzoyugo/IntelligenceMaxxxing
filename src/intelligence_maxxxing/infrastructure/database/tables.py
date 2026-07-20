"""ORM table definitions (internal only; never exposed as public contracts).

Designed for PostgreSQL. SQLite is used only in tests.

Append-only guarantees for `engine_events` and `audit_records` are enforced at
three levels: Python ports (no mutation methods), SQL triggers (reject
UPDATE/DELETE/TRUNCATE) and PostgreSQL role grants (runtime role has no
UPDATE/DELETE/TRUNCATE privilege). `projection_checkpoints` and identity
tables are mutable derived/administrative state - a documented exception.
"""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Float, Integer, String, UniqueConstraint
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
        # Aggregate identity is scoped by (tenant, owner, application): the
        # same aggregate_id may legitimately exist in two different
        # applications/owners without colliding. Optimistic concurrency and
        # aggregate lookups never cross an application boundary.
        UniqueConstraint(
            "tenant_id",
            "owner_id",
            "application_id",
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


class AcceptedObservationShadowRow(Base):
    """Shadow/staging copy of the accepted_observations projection.

    A rebuild replays events into this table first; verification compares its
    checksum with the live projection WITHOUT touching live rows. Only after a
    shadow build validates is it promoted atomically into
    `accepted_observations`. Identical column shape to the live table.
    """

    __tablename__ = "accepted_observations_shadow"

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


class EventStreamHeadRow(Base):
    """Transactional head of one (tenant, owner, application) integrity stream.

    The head is the single row that append() locks with SELECT ... FOR UPDATE
    so that concurrent writers of the same stream serialize and chain onto one
    another instead of forking on a stale previous hash. `status` is the real
    kill-switch: a QUARANTINED stream rejects every new append.
    """

    __tablename__ = "event_stream_heads"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    application_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_global_position: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_event_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stream_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    quarantine_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    broken_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quarantined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quarantine_audit_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IntegrityCheckpointRow(Base):
    """Last reliably verified point of one (tenant, owner, application) stream.

    INCREMENTAL verification resumes from here, using `last_verified_hash` as
    the anchor for the first event after the checkpoint. It is only advanced
    when verification of the newer range succeeds (never on failure)."""

    __tablename__ = "integrity_checkpoints"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    application_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_verified_global_position: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    last_verified_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_verified_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OK")


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


class CurrentHypothesisRow(Base):
    """Projection: current hypothesis state (rebuildable derived)."""

    __tablename__ = "current_hypotheses"

    hypothesis_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    domain_pack: Mapped[str] = mapped_column(String(64), nullable=False)
    template_id: Mapped[str] = mapped_column(String(128), nullable=False)
    template_version: Mapped[str] = mapped_column(String(16), nullable=False)
    statement: Mapped[str] = mapped_column(String(4000), nullable=False)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    causality_level: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    human_confirmed: Mapped[int] = mapped_column(Integer, nullable=False)
    parameters_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    experiment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audit_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    global_position: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CurrentExperimentRow(Base):
    """Projection: current experiment protocol (rebuildable derived)."""

    __tablename__ = "current_experiments"

    experiment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    hypothesis_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    protocol_version: Mapped[str] = mapped_column(String(16), nullable=False)
    analysis_method: Mapped[str] = mapped_column(String(128), nullable=False)
    baseline_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prospective_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prospective_target: Mapped[int] = mapped_column(Integer, nullable=False)
    maximum_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_group_size: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_meaningful_difference: Mapped[float] = mapped_column(Float, nullable=False)
    sleep_threshold_hours: Mapped[float] = mapped_column(Float, nullable=False)
    random_seed_policy: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    pre_registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    audit_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    global_position: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    activation_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    activation_global_position: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    activation_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class BeliefSnapshotRow(Base):
    """Projection: versioned belief snapshots (rebuildable derived)."""

    __tablename__ = "belief_snapshots"

    belief_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    hypothesis_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    evidence_id: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_belief_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    belief_state: Mapped[str] = mapped_column(String(64), nullable=False)
    model_probability: Mapped[float] = mapped_column(Float, nullable=False)
    credible_interval_low: Mapped[float] = mapped_column(Float, nullable=False)
    credible_interval_high: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_effect: Mapped[float] = mapped_column(Float, nullable=False)
    minimum_meaningful_difference: Mapped[float] = mapped_column(Float, nullable=False)
    data_confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    method_confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    conclusion_confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    recommendation_confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    calibration_state: Mapped[str] = mapped_column(String(32), nullable=False)
    causality_level: Mapped[str] = mapped_column(String(64), nullable=False)
    limitations_json: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    is_current: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    audit_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    global_position: Mapped[int] = mapped_column(BigInteger, nullable=False)


class EvidenceSnapshotRow(Base):
    """Projection: frozen evidence snapshots (rebuildable derived)."""

    __tablename__ = "evidence_snapshots"

    evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    hypothesis_id: Mapped[str] = mapped_column(String(64), nullable=False)
    experiment_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    phase: Mapped[str] = mapped_column(String(64), nullable=False)
    source_observation_ids: Mapped[list[object]] = mapped_column(JSON, nullable=False)
    source_event_ids: Mapped[list[object]] = mapped_column(JSON, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    eligible_count: Mapped[int] = mapped_column(Integer, nullable=False)
    excluded_count: Mapped[int] = mapped_column(Integer, nullable=False)
    exclusion_reasons: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    group_counts: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    descriptive_statistics: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    analysis_parameters: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    analysis_result: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    confounding_diagnostics: Mapped[list[object]] = mapped_column(JSON, nullable=False)
    limitations_json: Mapped[list[object]] = mapped_column(JSON, nullable=False)
    belief_state: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    audit_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    global_position: Mapped[int] = mapped_column(BigInteger, nullable=False)
    evidence_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_cutoff_global_position: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    evidence_cutoff_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    evaluation_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    evaluation_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    terminal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    terminal_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    critical_data_quality_failure: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_source_global_position: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_source_global_position: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class ExperimentProgressRow(Base):
    """Projection: live experiment progress counters."""

    __tablename__ = "experiment_progress"

    experiment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hypothesis_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False)
    baseline_eligible: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    baseline_sufficient: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    baseline_below: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prospective_eligible: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prospective_sufficient: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prospective_below: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prospective_target: Mapped[int] = mapped_column(Integer, nullable=False)
    window_days_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    current_belief_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    target_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sufficient_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    below_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    future_excluded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_source_excluded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    critical_data_quality_failure: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evaluation_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    terminal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    terminal_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    minimum_group_size: Mapped[int | None] = mapped_column(Integer, nullable=True)


class LearningHistoryRow(Base):
    """Projection: learning records (rebuildable derived)."""

    __tablename__ = "learning_history"

    learning_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    hypothesis_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    previous_belief_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_belief_id: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome_evaluation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    change_type: Mapped[str] = mapped_column(String(64), nullable=False)
    what_changed: Mapped[str] = mapped_column(String(2000), nullable=False)
    why_changed: Mapped[str] = mapped_column(String(2000), nullable=False)
    what_remains_unknown: Mapped[str] = mapped_column(String(2000), nullable=False)
    next_evidence_needed: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    audit_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    global_position: Mapped[int] = mapped_column(BigInteger, nullable=False)


class WellbeingFormulaVersionRow(Base):
    """Registered wellbeing formula versions (additive cache metadata)."""

    __tablename__ = "wellbeing_formula_versions"

    formula_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(16), primary_key=True)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)


class WellbeingBaselineRow(Base):
    __tablename__ = "wellbeing_baselines"

    baseline_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    formula_id: Mapped[str] = mapped_column(String(64), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(16), nullable=False)
    features_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    as_of_global_position: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class WellbeingFeatureSnapshotRow(Base):
    __tablename__ = "wellbeing_feature_snapshots"

    feature_snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    formula_id: Mapped[str] = mapped_column(String(64), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(16), nullable=False)
    period_start: Mapped[str] = mapped_column(String(32), nullable=False)
    period_end: Mapped[str] = mapped_column(String(32), nullable=False)
    features_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_days: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    as_of_global_position: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class WellbeingScoreSnapshotRow(Base):
    __tablename__ = "wellbeing_score_snapshots"

    score_snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    formula_id: Mapped[str] = mapped_column(String(64), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(16), nullable=False)
    feature_snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    happiness: Mapped[float | None] = mapped_column(Float, nullable=True)
    stress: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    early_warning: Mapped[str] = mapped_column(String(64), nullable=False)
    data_sufficiency: Mapped[str] = mapped_column(String(64), nullable=False)
    contributors_json: Mapped[list[object]] = mapped_column(JSON, nullable=False)
    suggested_actions_json: Mapped[list[object]] = mapped_column(JSON, nullable=False)
    explanation_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    as_of_global_position: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # V2 SHADOW additive fields (nullable; V1 rows untouched)
    formula_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    input_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    change_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    happiness_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    stress_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    sub_scores_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    plausible_range_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    happiness_acute: Mapped[float | None] = mapped_column(Float, nullable=True)
    happiness_chronic: Mapped[float | None] = mapped_column(Float, nullable=True)
    stress_acute: Mapped[float | None] = mapped_column(Float, nullable=True)
    stress_chronic: Mapped[float | None] = mapped_column(Float, nullable=True)
    stress_anticipatory: Mapped[float | None] = mapped_column(Float, nullable=True)


class WellbeingFeedbackRow(Base):
    __tablename__ = "wellbeing_feedback"

    feedback_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    score_snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rating: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
