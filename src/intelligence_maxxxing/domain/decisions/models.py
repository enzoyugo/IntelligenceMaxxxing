"""Decision contract (Constitution Arts. 18-19, 24-25).

Stage 0 status: CONTRACT_ONLY.
"""

from enum import StrEnum

from pydantic import Field

from intelligence_maxxxing.domain.common.base import CanonicalObject


class Reversibility(StrEnum):
    REVERSIBLE = "REVERSIBLE"
    PARTIALLY_REVERSIBLE = "PARTIALLY_REVERSIBLE"
    IRREVERSIBLE = "IRREVERSIBLE"


class Decision(CanonicalObject):
    """A recorded human or authorized decision, kept separate from its outcome."""

    audit_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    decided_by: str = Field(min_length=1)
    reversibility: Reversibility
    recommendation_id: str | None = None
    disagreed_with_recommendation: bool = False
    human_reasons: str | None = None
