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
