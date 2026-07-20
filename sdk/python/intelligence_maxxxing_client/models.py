"""Public SDK models mirroring the public API contract (not Core internals)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EnvelopeMeta(BaseModel):
    # Tolerant on input: the server may add meta fields within the same major version.
    model_config = ConfigDict(extra="ignore")

    request_id: str
    engine_version: str
    api_version: str
    domain_pack: str = "core"
    generated_at: str
    audit_id: str | None = None
    health: dict[str, str] = Field(default_factory=dict)
    freshness: dict[str, str] = Field(default_factory=dict)


class HealthView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str
    service: str
    engine_version: str
    constitution_version: str
    meta: EnvelopeMeta


class ObservationAcceptedView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    observation_id: str
    event_id: str
    audit_id: str
    replayed: bool
    meta: EnvelopeMeta


class ObservationView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    observation_id: str
    schema_version: str
    domain_pack: str
    subject: str
    statement: str
    knowledge_class: str
    unknown_reason: str | None = None
    observed_by: str
    context: dict[str, Any] = Field(default_factory=dict)
    source_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    occurred_at: str | None = None
    created_at: str
    audit_id: str
    event_id: str
    global_position: int


class ObservationListView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[ObservationView]
    next_cursor: int | None = None
    projection_name: str
    projection_version: str
    projection_position: int | None = None
    projection_updated_at: str | None = None
    meta: EnvelopeMeta


class AuditEventView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int
    domain_pack: str
    schema_version: str
    payload: dict[str, Any]
    occurred_at: str
    recorded_at: str


class AuditView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    audit_id: str
    request_id: str
    engine_version: str
    api_version: str
    schema_version: str
    domain_pack: str
    actor_type: str
    actor_id: str
    action: str
    input_object_ids: list[str]
    output_object_ids: list[str]
    event_ids: list[str]
    timestamp: str
    events: list[AuditEventView] = Field(default_factory=list)
    meta: EnvelopeMeta


class HypothesisParameters(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sleep_threshold_hours: float
    minimum_meaningful_difference: float = 0.5
    prospective_target: int = 30
    maximum_window_days: int = 60


class HypothesisWriteResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hypothesis_id: str
    event_id: str
    audit_id: str
    replayed: bool
    experiment_id: str | None = None
    meta: EnvelopeMeta


class HypothesisView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hypothesis_id: str
    template_id: str
    template_version: str
    statement: str
    direction: str
    causality_level: str
    status: str
    human_confirmed: bool
    parameters: dict[str, Any] | None = None
    proposed_at: str
    activated_at: str | None = None
    retired_at: str | None = None
    experiment_id: str | None = None
    audit_id: str
    event_id: str


class HypothesisListView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[HypothesisView]
    meta: EnvelopeMeta


class ExperimentView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    experiment_id: str
    hypothesis_id: str
    protocol_version: str
    analysis_method: str
    baseline_cutoff: str
    prospective_start: str
    prospective_target: int
    maximum_window_days: int
    minimum_group_size: int
    minimum_meaningful_difference: float
    sleep_threshold_hours: float
    random_seed_policy: str
    status: str
    pre_registered_at: str
    audit_id: str
    event_id: str


class ExperimentProgressView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    experiment_id: str
    hypothesis_id: str
    baseline_eligible: int
    baseline_sufficient: int
    baseline_below: int
    prospective_eligible: int
    prospective_sufficient: int
    prospective_below: int
    prospective_target: int
    window_days_remaining: int | None = None
    status: str
    current_belief_state: str | None = None
    last_evaluated_at: str | None = None
    updated_at: str
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


class EvaluateExperimentResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    experiment_id: str
    evidence_id: str
    belief_id: str
    belief_state: str
    event_id: str
    audit_id: str
    replayed: bool
    evaluation_kind: str | None = None
    terminal: bool = False
    terminal_reason: str | None = None
    prospective_eligible: int = 0
    prospective_target: int = 0
    target_remaining: int = 0
    sufficient_count: int = 0
    below_count: int = 0
    sufficient_remaining: int = 0
    below_remaining: int = 0
    future_excluded: int = 0
    duplicate_source_excluded: int = 0
    critical_data_quality_failure: bool = False
    meta: EnvelopeMeta


class BeliefView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    belief_id: str
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
    limitations: list[str] = Field(default_factory=list)
    is_current: bool
    created_at: str
    audit_id: str
    event_id: str


class BeliefListView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[BeliefView]
    meta: EnvelopeMeta


class LearningView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    learning_id: str
    hypothesis_id: str
    previous_belief_id: str | None = None
    new_belief_id: str
    outcome_evaluation_id: str
    change_type: str
    what_changed: str
    why_changed: str
    what_remains_unknown: str
    next_evidence_needed: str
    created_at: str
    audit_id: str
    event_id: str


class LearningListView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[LearningView]
    meta: EnvelopeMeta
