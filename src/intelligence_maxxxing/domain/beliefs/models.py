"""Belief contracts.

Stage 0 `Belief` remains the constitutional immutable KnowledgeObject.
Applications and LLMs can never write beliefs via HTTP (enforced by tests).
Stage 3 `BeliefSnapshot` is the versioned operational belief derived by the
Engine during evaluation — created only through governed use cases.
"""

from pydantic import Field, model_validator

from intelligence_maxxxing.domain.common.base import CanonicalObject
from intelligence_maxxxing.domain.common.confidence import ConfidenceComponents
from intelligence_maxxxing.domain.common.epistemic import (
    BeliefState,
    CalibrationState,
    CausalityLevel,
    ConfidenceLevel,
    KnowledgeClass,
)
from intelligence_maxxxing.domain.common.knowledge import KnowledgeObject


class Belief(KnowledgeObject):
    """An operational belief derived from governed evidence, never from raw client input."""

    knowledge_class: KnowledgeClass = KnowledgeClass.OPERATIONAL_BELIEF
    confidence: ConfidenceComponents
    supporting_evidence_ids: tuple[str, ...] = Field(min_length=1)
    revalidation_policy: str = Field(
        min_length=1,
        description="Conditions under which this belief must be revalidated (Art. 11)",
    )
    supersedes_belief_id: str | None = None

    @model_validator(mode="after")
    def _must_stay_operational_belief(self) -> "Belief":
        if self.knowledge_class is not KnowledgeClass.OPERATIONAL_BELIEF:
            raise ValueError("a Belief object must keep knowledge_class=OPERATIONAL_BELIEF")
        return self


class BeliefSnapshot(CanonicalObject):
    """Versioned belief produced by a Stage 3 evaluation. History is append-only."""

    hypothesis_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    previous_belief_id: str | None = None
    owner_id: str = Field(min_length=1)
    application_id: str = Field(min_length=1)
    belief_state: BeliefState
    model_probability: float = Field(ge=0.0, le=1.0)
    credible_interval_low: float
    credible_interval_high: float
    estimated_effect: float
    minimum_meaningful_difference: float
    data_confidence: ConfidenceLevel
    method_confidence: ConfidenceLevel
    conclusion_confidence: ConfidenceLevel
    recommendation_confidence: ConfidenceLevel = ConfidenceLevel.VERY_LOW
    calibration_state: CalibrationState = CalibrationState.UNCALIBRATED
    causality_level: CausalityLevel = CausalityLevel.CORRELATION
    limitations: tuple[str, ...] = ()
    audit_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _stage3_invariants(self) -> "BeliefSnapshot":
        if self.causality_level is not CausalityLevel.CORRELATION:
            raise ValueError("Stage 3 beliefs must keep causality_level=CORRELATION")
        if self.recommendation_confidence is not ConfidenceLevel.VERY_LOW:
            raise ValueError(
                "Stage 3 produces no recommendations: recommendation_confidence=VERY_LOW"
            )
        if self.calibration_state is not CalibrationState.UNCALIBRATED:
            raise ValueError("Stage 3 beliefs remain UNCALIBRATED")
        if self.credible_interval_low > self.credible_interval_high:
            raise ValueError("credible interval low cannot exceed high")
        return self
