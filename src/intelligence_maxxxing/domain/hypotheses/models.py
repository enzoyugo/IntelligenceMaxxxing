"""Hypothesis aggregate (Constitution Arts. 12-13; Stage 3 first epistemic loop).

History is append-only via events. Current status lives in a rebuildable
projection. Parameters confirmed at activation are immutable thereafter —
changing them requires retiring and proposing a new version.
"""

from pydantic import Field, model_validator

from intelligence_maxxxing.domain.common.base import CanonicalObject, DomainModel, UtcDatetime
from intelligence_maxxxing.domain.common.epistemic import (
    CausalityLevel,
    HypothesisStatus,
    KnowledgeClass,
)


class HypothesisParameters(DomainModel):
    """Human-confirmed protocol parameters. Frozen after activation."""

    sleep_threshold_hours: float = Field(ge=6.0, le=10.0)
    minimum_meaningful_difference: float = Field(ge=0.25, le=2.0)
    prospective_target: int = Field(ge=14, le=42)
    maximum_window_days: int = Field(ge=21, le=90)


class Hypothesis(CanonicalObject):
    """A testable, human-confirmed assertion. Generation is free; promotion is governed."""

    knowledge_class: KnowledgeClass = KnowledgeClass.HYPOTHESIS
    owner_id: str = Field(min_length=1)
    application_id: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    template_version: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    direction: str = Field(default="POSITIVE", min_length=1)
    causality_level: CausalityLevel = CausalityLevel.CORRELATION
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    human_confirmed: bool = False
    parameters: HypothesisParameters | None = None
    proposed_at: UtcDatetime
    activated_at: UtcDatetime | None = None
    retired_at: UtcDatetime | None = None
    audit_id: str = Field(min_length=1)
    experiment_id: str | None = None

    @model_validator(mode="after")
    def _must_stay_hypothesis(self) -> "Hypothesis":
        if self.knowledge_class is not KnowledgeClass.HYPOTHESIS:
            raise ValueError("a Hypothesis object must keep knowledge_class=HYPOTHESIS")
        if self.causality_level is not CausalityLevel.CORRELATION:
            raise ValueError(
                "Stage 3 hypotheses are observational: causality_level must be CORRELATION"
            )
        return self
