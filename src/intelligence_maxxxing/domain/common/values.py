"""Human value contract (Constitution Art. 22, Epistemic Standard §11).

Values cannot be deduced from data alone. Inferred values may be suggested but
are not authoritative until confirmed by the human.
"""

from enum import StrEnum

from intelligence_maxxxing.domain.common.epistemic import KnowledgeClass
from intelligence_maxxxing.domain.common.knowledge import KnowledgeObject


class ValueOrigin(StrEnum):
    STATED = "STATED"
    REVEALED_BY_BEHAVIOR = "REVEALED_BY_BEHAVIOR"
    INFERRED_SUGGESTION = "INFERRED_SUGGESTION"


class HumanValue(KnowledgeObject):
    """A human preference or priority."""

    knowledge_class: KnowledgeClass = KnowledgeClass.HUMAN_VALUE
    origin: ValueOrigin
    confirmed_by_owner: bool = False
