"""Hypothesis contract (Constitution Arts. 12-13).

Stage 0 status: CONTRACT_ONLY. No hypothesis generation exists yet.
"""

from pydantic import Field, model_validator

from intelligence_maxxxing.domain.common.epistemic import HypothesisStatus, KnowledgeClass
from intelligence_maxxxing.domain.common.knowledge import KnowledgeObject


class Hypothesis(KnowledgeObject):
    """A testable assertion. Generation is free; promotion is governed."""

    knowledge_class: KnowledgeClass = KnowledgeClass.HYPOTHESIS
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    origin: str = Field(min_length=1, description="What motivated this hypothesis")
    expected_mechanism: str | None = None
    post_hoc: bool = Field(
        default=False,
        description="Generated after observing an outcome; requires new validation data",
    )

    @model_validator(mode="after")
    def _must_stay_hypothesis(self) -> "Hypothesis":
        if self.knowledge_class is not KnowledgeClass.HYPOTHESIS:
            raise ValueError("a Hypothesis object must keep knowledge_class=HYPOTHESIS")
        return self
