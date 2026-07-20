"""Learning contracts (Constitution Art. 51).

`Learning` remains the Stage 0 stub.
`LearningRecord` is the Stage 3 deterministic template record.
"""

from pydantic import Field

from intelligence_maxxxing.domain.common.base import CanonicalObject
from intelligence_maxxxing.domain.common.epistemic import LearningChangeType


class Learning(CanonicalObject):
    """Knowledge produced by comparing decisions, outcomes and expectations."""

    audit_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    derived_from_outcome_ids: tuple[str, ...] = Field(min_length=1)
    changes_proposed: tuple[str, ...] = ()


class LearningRecord(CanonicalObject):
    """Knowledge produced by comparing prior and new beliefs after an outcome."""

    hypothesis_id: str = Field(min_length=1)
    previous_belief_id: str | None = None
    new_belief_id: str = Field(min_length=1)
    outcome_evaluation_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    application_id: str = Field(min_length=1)
    change_type: LearningChangeType
    what_changed: str = Field(min_length=1)
    why_changed: str = Field(min_length=1)
    what_remains_unknown: str = Field(min_length=1)
    next_evidence_needed: str = Field(min_length=1)
    audit_id: str = Field(min_length=1)
