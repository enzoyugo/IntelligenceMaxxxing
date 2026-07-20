"""Public contracts for /api/v1/hypotheses (Stage 3 epistemic loop)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from intelligence_maxxxing.domain.hypotheses.models import HypothesisParameters


class ProposeHypothesisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameters: HypothesisParameters | None = None
    human_confirmed: bool = False


class ProposeHypothesisData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str
    event_id: str
    audit_id: str
    replayed: bool


class ActivateHypothesisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameters: HypothesisParameters


class ActivateHypothesisData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str
    experiment_id: str
    event_id: str
    audit_id: str
    replayed: bool


class RetireHypothesisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1)


class RetireHypothesisData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_id: str
    event_id: str
    audit_id: str
    replayed: bool


class HypothesisView(BaseModel):
    model_config = ConfigDict(extra="forbid")

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


class HypothesisListData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[HypothesisView, ...]


class BeliefView(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    limitations: tuple[str, ...]
    is_current: bool
    created_at: str
    audit_id: str
    event_id: str


class BeliefListData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[BeliefView, ...]


class LearningView(BaseModel):
    model_config = ConfigDict(extra="forbid")

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


class LearningListData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[LearningView, ...]
