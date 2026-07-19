"""Outcome contract (Constitution Arts. 19, 27-28).

Decision quality and outcome are evaluated separately; an outcome never
rewrites the decision that produced it.

Stage 0 status: CONTRACT_ONLY.
"""

from pydantic import Field

from intelligence_maxxxing.domain.common.base import CanonicalObject


class Outcome(CanonicalObject):
    """What actually happened after a decision."""

    audit_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    impact_notes: str | None = None
    luck_assessment: str | None = Field(
        default=None,
        description="Estimated non-predictable component; never rewrites decision quality",
    )
