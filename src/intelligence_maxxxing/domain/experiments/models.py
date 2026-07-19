"""Experiment contract (Epistemic Standard §10).

Stage 0 status: CONTRACT_ONLY. Pre-registration fields exist so a material
experiment cannot be created without a declared design.
"""

from pydantic import Field

from intelligence_maxxxing.domain.common.base import CanonicalObject


class Experiment(CanonicalObject):
    """A pre-registered experiment design tied to a hypothesis."""

    hypothesis_id: str = Field(min_length=1)
    audit_id: str = Field(min_length=1)
    outcome_definition: str = Field(min_length=1)
    metrics: tuple[str, ...] = Field(min_length=1)
    population: str = Field(min_length=1)
    success_criteria: str = Field(min_length=1)
    abandonment_criteria: str = Field(min_length=1)
    analysis_plan: str = Field(min_length=1)
    baseline: str | None = None
    risk_limits: str | None = None
