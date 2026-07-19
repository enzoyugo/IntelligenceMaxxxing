"""Learning contract (Constitution Art. 51: the worst sin is not to learn).

Stage 0 status: CONTRACT_ONLY.
"""

from pydantic import Field

from intelligence_maxxxing.domain.common.base import CanonicalObject


class Learning(CanonicalObject):
    """Knowledge produced by comparing decisions, outcomes and expectations."""

    audit_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    derived_from_outcome_ids: tuple[str, ...] = Field(min_length=1)
    changes_proposed: tuple[str, ...] = ()
