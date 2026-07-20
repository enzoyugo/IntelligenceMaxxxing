"""Epistemic-loop event payloads (Stage 3).

Every payload is a frozen Pydantic model. The event store validates against
these schemas before append. History is append-only; projections derive state.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _EventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class HypothesisProposedPayload(_EventPayload):
    hypothesis_id: str
    template_id: str
    template_version: str
    statement: str
    direction: str
    causality_level: str
    parameters: dict[str, Any] | None = None
    human_confirmed: bool = False


class HypothesisActivatedPayload(_EventPayload):
    hypothesis_id: str
    experiment_id: str
    parameters: dict[str, Any]
    baseline_cutoff: str
    prospective_start: str
    prospective_target: int
    maximum_window_days: int


class HypothesisRetiredPayload(_EventPayload):
    hypothesis_id: str
    reason: str
    previous_status: str


class ExperimentRegisteredPayload(_EventPayload):
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


class ExperimentObservationWindowOpenedPayload(_EventPayload):
    experiment_id: str
    hypothesis_id: str
    phase: str
    opened_at: str


class EvidenceEvaluatedPayload(_EventPayload):
    evidence_id: str
    hypothesis_id: str
    experiment_id: str
    phase: str
    source_observation_ids: list[str]
    source_event_ids: list[str]
    source_hash: str
    eligible_count: int
    excluded_count: int
    exclusion_reasons: dict[str, int]
    group_counts: dict[str, int]
    analysis_result: dict[str, Any] | None = None
    belief_state: str
    limitations: list[str] = Field(default_factory=list)
    descriptive_statistics: dict[str, Any] = Field(default_factory=dict)
    analysis_parameters: dict[str, Any] = Field(default_factory=dict)
    confounding_diagnostics: list[dict[str, Any]] = Field(default_factory=list)


class BeliefCreatedPayload(_EventPayload):
    belief_id: str
    hypothesis_id: str
    evidence_id: str
    belief_state: str
    model_probability: float
    estimated_effect: float
    calibration_state: str
    causality_level: str
    previous_belief_id: str | None = None
    credible_interval_low: float = 0.0
    credible_interval_high: float = 0.0
    minimum_meaningful_difference: float = 0.0
    data_confidence: str = "LOW"
    method_confidence: str = "MODERATE"
    conclusion_confidence: str = "LOW"
    recommendation_confidence: str = "VERY_LOW"
    limitations: list[str] = Field(default_factory=list)


class BeliefUpdatedPayload(_EventPayload):
    belief_id: str
    hypothesis_id: str
    evidence_id: str
    previous_belief_id: str
    belief_state: str
    model_probability: float
    estimated_effect: float
    calibration_state: str
    causality_level: str
    credible_interval_low: float = 0.0
    credible_interval_high: float = 0.0
    minimum_meaningful_difference: float = 0.0
    data_confidence: str = "LOW"
    method_confidence: str = "MODERATE"
    conclusion_confidence: str = "LOW"
    recommendation_confidence: str = "VERY_LOW"
    limitations: list[str] = Field(default_factory=list)


class OutcomeEvaluatedPayload(_EventPayload):
    outcome_evaluation_id: str
    hypothesis_id: str
    experiment_id: str
    prior_belief_id: str | None
    validation_evidence_id: str
    validation_result: str
    agreement_with_prior: str
    outcome_state: str


class LearningRecordedPayload(_EventPayload):
    learning_id: str
    hypothesis_id: str
    previous_belief_id: str | None
    new_belief_id: str
    outcome_evaluation_id: str
    change_type: str
    what_changed: str
    why_changed: str
    what_remains_unknown: str
    next_evidence_needed: str


class ExperimentCompletedPayload(_EventPayload):
    experiment_id: str
    hypothesis_id: str
    final_belief_state: str
    evidence_id: str


class ExperimentExpiredInconclusivePayload(_EventPayload):
    experiment_id: str
    hypothesis_id: str
    reason: str
    group_counts: dict[str, int]
