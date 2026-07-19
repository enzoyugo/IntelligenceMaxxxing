"""Base contract for knowledge objects.

Constitutional protections implemented here:
- knowledge_class is REQUIRED with no default: an inference can never silently
  become a fact (Constitution Art. 6, prohibition 9).
- UNKNOWN always requires a reason (Epistemic Standard §3).
- audit_id is REQUIRED: no material knowledge object exists without audit
  (Epistemic Standard §12, Governance §7).
"""

from pydantic import Field, model_validator

from intelligence_maxxxing.domain.common.base import CanonicalObject
from intelligence_maxxxing.domain.common.confidence import ConfidenceComponents
from intelligence_maxxxing.domain.common.epistemic import (
    CausalityLevel,
    FreshnessState,
    KnowledgeClass,
    UnknownReason,
)


class KnowledgeObject(CanonicalObject):
    """Common fields for every material knowledge object."""

    # No default on purpose: the caller must declare what kind of knowledge this is.
    knowledge_class: KnowledgeClass
    unknown_reason: UnknownReason | None = None
    statement: str = Field(min_length=1)
    audit_id: str = Field(min_length=1)
    confidence: ConfidenceComponents | None = None
    causality_level: CausalityLevel | None = None
    freshness_state: FreshnessState = FreshnessState.UNKNOWN
    limitations: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _unknown_requires_reason(self) -> "KnowledgeObject":
        if self.knowledge_class is KnowledgeClass.UNKNOWN and self.unknown_reason is None:
            raise ValueError("UNKNOWN knowledge requires an unknown_reason")
        if self.knowledge_class is not KnowledgeClass.UNKNOWN and self.unknown_reason is not None:
            raise ValueError("unknown_reason is only valid when knowledge_class is UNKNOWN")
        return self
