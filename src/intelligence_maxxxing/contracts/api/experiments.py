"""Public contracts for /api/v1/experiments (Stage 3 epistemic loop)."""

from pydantic import BaseModel, ConfigDict

from intelligence_maxxxing.domain.common.epistemic import EvidencePhase


class EvaluateExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: EvidencePhase


class EvaluateExperimentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    evidence_id: str
    belief_id: str
    belief_state: str
    event_id: str
    audit_id: str
    replayed: bool
    evaluation_kind: str
    terminal: bool
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


class ExperimentView(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    activation_event_id: str | None = None
    activation_global_position: int | None = None
    activation_recorded_at: str | None = None


class ExperimentProgressView(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
