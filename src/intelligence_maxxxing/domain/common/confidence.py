"""Confidence contract (Epistemic Standard §4).

Stage 0 defines the structure only. No statistical computation is implemented
and none is simulated: values must be provided explicitly by a governed method.
"""

from pydantic import Field, model_validator

from intelligence_maxxxing.domain.common.base import DomainModel
from intelligence_maxxxing.domain.common.epistemic import ConfidenceLevel

Probability = float


class ConfidenceComponents(DomainModel):
    """Decomposed confidence; a single number may be shown but components stay auditable."""

    data_confidence: ConfidenceLevel | None = None
    method_confidence: ConfidenceLevel | None = None
    conclusion_confidence: ConfidenceLevel | None = None
    recommendation_confidence: ConfidenceLevel | None = None
    point_estimate: Probability | None = Field(default=None, ge=0.0, le=1.0)
    interval_low: Probability | None = Field(default=None, ge=0.0, le=1.0)
    interval_high: Probability | None = Field(default=None, ge=0.0, le=1.0)
    explanation: str | None = None

    @model_validator(mode="after")
    def _validate_interval(self) -> "ConfidenceComponents":
        if (self.interval_low is None) != (self.interval_high is None):
            raise ValueError("interval_low and interval_high must be provided together")
        if (
            self.interval_low is not None
            and self.interval_high is not None
            and self.interval_low > self.interval_high
        ):
            raise ValueError("interval_low cannot exceed interval_high")
        return self
