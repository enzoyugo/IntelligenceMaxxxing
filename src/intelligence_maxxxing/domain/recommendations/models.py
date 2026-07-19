"""Recommendation contract (Engine Service Contract §8; Governance §7.2).

Stage 0 status: CONTRACT_ONLY. No recommendations are produced yet.
"""

from pydantic import Field

from intelligence_maxxxing.domain.common.base import CanonicalObject
from intelligence_maxxxing.domain.common.confidence import ConfidenceComponents


class Recommendation(CanonicalObject):
    """An explained, audited, confidence-decomposed recommendation."""

    audit_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    confidence: ConfidenceComponents
    based_on_belief_ids: tuple[str, ...] = Field(min_length=1)
    known_limitations: tuple[str, ...] = ()
    required_human_action: str | None = None
