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


class ProjectedHypothesis(BaseModel):
    """One row of the current_hypotheses projection (derived state)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hypothesis_id: str
    tenant_id: str
    owner_id: str
    application_id: str
    domain_pack: str
    template_id: str
    template_version: str
    statement: str
    direction: str
    causality_level: str
    status: str
    human_confirmed: bool
    parameters: dict[str, object] | None = None
    proposed_at: datetime
    activated_at: datetime | None = None
    retired_at: datetime | None = None
    experiment_id: str | None = None
    audit_id: str
    event_id: str
    global_position: int
    updated_at: datetime


class ProjectedExperiment(BaseModel):
    """One row of the current_experiments projection (derived state)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_id: str
    tenant_id: str
    owner_id: str
    application_id: str
    hypothesis_id: str
    protocol_version: str
    analysis_method: str
    baseline_cutoff: datetime
    prospective_start: datetime
    prospective_target: int
    maximum_window_days: int
    minimum_group_size: int
    minimum_meaningful_difference: float
    sleep_threshold_hours: float
    random_seed_policy: str
    status: str
    pre_registered_at: datetime
    audit_id: str
    event_id: str
    global_position: int
    updated_at: datetime
    activation_event_id: str | None = None
    activation_global_position: int | None = None
    activation_recorded_at: datetime | None = None


class ProjectedBeliefSnapshot(BaseModel):
    """One row of the belief_snapshots projection (derived, versioned)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    belief_id: str
    tenant_id: str
    owner_id: str
    application_id: str
    hypothesis_id: str
    evidence_id: str
    previous_belief_id: str | None = None
    belief_state: str
    model_probability: float
    credible_interval_low: float
    credible_interval_high: float
    estimated_effect: float
    minimum_meaningful_difference: float
    data_confidence: str
    method_confidence: str
    conclusion_confidence: str
    recommendation_confidence: str
    calibration_state: str
    causality_level: str
    limitations: tuple[str, ...] = ()
    is_current: bool = False
    created_at: datetime
    audit_id: str
    event_id: str
    global_position: int


class ProjectedEvidenceSnapshot(BaseModel):
    """One row of the evidence_snapshots projection (derived state)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    tenant_id: str
    owner_id: str
    application_id: str
    hypothesis_id: str
    experiment_id: str
    phase: str
    source_observation_ids: tuple[str, ...]
    source_event_ids: tuple[str, ...]
    source_hash: str
    eligible_count: int
    excluded_count: int
    exclusion_reasons: dict[str, int] = Field(default_factory=dict)
    group_counts: dict[str, int] = Field(default_factory=dict)
    descriptive_statistics: dict[str, object] = Field(default_factory=dict)
    analysis_parameters: dict[str, object] = Field(default_factory=dict)
    analysis_result: dict[str, object] | None = None
    confounding_diagnostics: tuple[dict[str, object], ...] = ()
    limitations: tuple[str, ...] = ()
    belief_state: str
    generated_at: datetime
    audit_id: str
    event_id: str
    global_position: int
    evidence_fingerprint: str | None = None
    evidence_cutoff_global_position: int | None = None
    evidence_cutoff_recorded_at: datetime | None = None
    evaluation_started_at: datetime | None = None
    evaluation_kind: str | None = None
    terminal: bool = False
    terminal_reason: str | None = None
    critical_data_quality_failure: bool = False
    source_count: int = 0
    first_source_global_position: int | None = None
    last_source_global_position: int | None = None


class ProjectedExperimentProgress(BaseModel):
    """Live experiment progress counters (derived state)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_id: str
    hypothesis_id: str
    tenant_id: str
    owner_id: str
    application_id: str
    baseline_eligible: int = 0
    baseline_sufficient: int = 0
    baseline_below: int = 0
    prospective_eligible: int = 0
    prospective_sufficient: int = 0
    prospective_below: int = 0
    prospective_target: int
    window_days_remaining: int | None = None
    status: str
    current_belief_state: str | None = None
    last_evaluated_at: datetime | None = None
    updated_at: datetime
    target_remaining: int | None = None
    sufficient_remaining: int | None = None
    below_remaining: int | None = None
    future_excluded: int = 0
    duplicate_source_excluded: int = 0
    critical_data_quality_failure: bool = False
    evaluation_kind: str | None = None
    terminal: bool = False
    terminal_reason: str | None = None
    minimum_group_size: int | None = None


class ProjectedLearningRecord(BaseModel):
    """One row of the learning_history projection (derived state)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    learning_id: str
    tenant_id: str
    owner_id: str
    application_id: str
    hypothesis_id: str
    previous_belief_id: str | None = None
    new_belief_id: str
    outcome_evaluation_id: str
    change_type: str
    what_changed: str
    why_changed: str
    what_remains_unknown: str
    next_evidence_needed: str
    created_at: datetime
    audit_id: str
    event_id: str
    global_position: int


class EpistemicStorePort(ABC):
    """Stage 3 epistemic projections: hypotheses, experiments, beliefs, evidence."""

    @abstractmethod
    def upsert_hypothesis(self, row: ProjectedHypothesis) -> None: ...

    @abstractmethod
    def get_hypothesis(
        self, owner_id: str, application_id: str, hypothesis_id: str
    ) -> ProjectedHypothesis | None: ...

    @abstractmethod
    def list_hypotheses(
        self, owner_id: str, application_id: str, *, limit: int = 50
    ) -> Sequence[ProjectedHypothesis]: ...

    @abstractmethod
    def upsert_experiment(self, row: ProjectedExperiment) -> None: ...

    @abstractmethod
    def get_experiment(
        self, owner_id: str, application_id: str, experiment_id: str
    ) -> ProjectedExperiment | None: ...

    @abstractmethod
    def get_experiment_for_hypothesis(
        self, owner_id: str, application_id: str, hypothesis_id: str
    ) -> ProjectedExperiment | None: ...

    @abstractmethod
    def upsert_belief_snapshot(self, row: ProjectedBeliefSnapshot) -> None:
        """Append/update belief snapshot; marks prior rows for the hypothesis not current."""

    @abstractmethod
    def get_belief_snapshot(
        self, owner_id: str, application_id: str, belief_id: str
    ) -> ProjectedBeliefSnapshot | None: ...

    @abstractmethod
    def get_current_belief(
        self, owner_id: str, application_id: str, hypothesis_id: str
    ) -> ProjectedBeliefSnapshot | None: ...

    @abstractmethod
    def list_belief_snapshots(
        self, owner_id: str, application_id: str, hypothesis_id: str
    ) -> Sequence[ProjectedBeliefSnapshot]: ...

    @abstractmethod
    def upsert_evidence_snapshot(self, row: ProjectedEvidenceSnapshot) -> None: ...

    @abstractmethod
    def get_evidence_snapshot(
        self, owner_id: str, application_id: str, evidence_id: str
    ) -> ProjectedEvidenceSnapshot | None: ...

    @abstractmethod
    def get_evidence_by_fingerprint(
        self,
        owner_id: str,
        application_id: str,
        experiment_id: str,
        phase: str,
        evidence_fingerprint: str,
    ) -> ProjectedEvidenceSnapshot | None: ...

    @abstractmethod
    def upsert_experiment_progress(self, row: ProjectedExperimentProgress) -> None: ...

    @abstractmethod
    def get_experiment_progress(
        self, owner_id: str, application_id: str, experiment_id: str
    ) -> ProjectedExperimentProgress | None: ...

    @abstractmethod
    def append_learning_record(self, row: ProjectedLearningRecord) -> None: ...

    @abstractmethod
    def list_learning_records(
        self, owner_id: str, application_id: str, hypothesis_id: str
    ) -> Sequence[ProjectedLearningRecord]: ...

    @abstractmethod
    def delete_all_epistemic_projections(self) -> int:
        """Clear all Stage 3 epistemic projection tables (rebuildable derived state)."""

    @abstractmethod
    def list_all_hypotheses(self) -> Sequence[ProjectedHypothesis]: ...

    @abstractmethod
    def list_all_experiments(self) -> Sequence[ProjectedExperiment]: ...

    @abstractmethod
    def list_all_belief_snapshots(self) -> Sequence[ProjectedBeliefSnapshot]: ...

    @abstractmethod
    def list_all_evidence_snapshots(self) -> Sequence[ProjectedEvidenceSnapshot]: ...

    @abstractmethod
    def list_all_experiment_progress(self) -> Sequence[ProjectedExperimentProgress]: ...

    @abstractmethod
    def list_all_learning_records(self) -> Sequence[ProjectedLearningRecord]: ...


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
    epistemic: EpistemicStorePort

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
