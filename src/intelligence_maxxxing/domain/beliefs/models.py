"""Belief contract (Constitution Arts. 11, 41; Technical Architecture §8).

Stage 0 status: CONTRACT_ONLY. There is no Belief Engine yet.

Constitutional protections encoded in the contract:
- beliefs are frozen; a new version is a new object, history is never mutated;
- beliefs require confidence components and an audit_id;
- applications and LLMs can never write beliefs: there is no public write
  contract for beliefs, and constitutional tests protect this boundary.
"""

from pydantic import Field, model_validator

from intelligence_maxxxing.domain.common.confidence import ConfidenceComponents
from intelligence_maxxxing.domain.common.epistemic import KnowledgeClass
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
