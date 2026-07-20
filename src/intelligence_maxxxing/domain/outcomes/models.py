"""Outcome contracts (Constitution Arts. 19, 27-28).

`Outcome` remains the Stage 0 decision-outcome stub.
`OutcomeEvaluation` is the Stage 3 prospective-vs-prior comparison.
"""

from pydantic import Field

from intelligence_maxxxing.domain.common.base import CanonicalObject
from intelligence_maxxxing.domain.common.epistemic import AgreementWithPrior, BeliefState


class Outcome(CanonicalObject):
    """What actually happened after a decision (Stage 0 contract)."""

    audit_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    impact_notes: str | None = None
    luck_assessment: str | None = Field(
        default=None,
        description="Estimated non-predictable component; never rewrites decision quality",
    )


class OutcomeEvaluation(CanonicalObject):
    """Frozen comparison of prospective validation against the prior belief."""

    hypothesis_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    application_id: str = Field(min_length=1)
    prior_belief_id: str | None = None
    validation_evidence_id: str = Field(min_length=1)
    validation_result: BeliefState
    agreement_with_prior: AgreementWithPrior
    outcome_state: str = Field(min_length=1)
    audit_id: str = Field(min_length=1)
