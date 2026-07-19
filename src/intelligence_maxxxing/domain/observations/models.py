"""Observation: the only canonical object fully persisted in Stage 0."""

from pydantic import Field, model_validator

from intelligence_maxxxing.domain.common.epistemic import KnowledgeClass
from intelligence_maxxxing.domain.common.knowledge import KnowledgeObject

# Observations enter the Engine as raw registered knowledge. They may be
# observed facts, human observations classified as such, or explicit unknowns.
_ALLOWED_OBSERVATION_CLASSES = frozenset(
    {
        KnowledgeClass.OBSERVED_FACT,
        KnowledgeClass.DERIVED_FACT,
        KnowledgeClass.HUMAN_VALUE,
        KnowledgeClass.UNKNOWN,
    }
)


class Observation(KnowledgeObject):
    """An accepted observation submitted by an application or a human.

    Constitutional constraints:
    - it can never be classified as INFERENCE, HYPOTHESIS or a conclusion class
      (Constitution Art. 6: states must not be conflated);
    - it always carries an audit_id (assigned by the Engine on acceptance);
    - it is frozen: acceptance never mutates history (Law 9).
    """

    observed_by: str = Field(min_length=1, description="Observer identity (human or system)")

    @model_validator(mode="after")
    def _observation_class_is_valid(self) -> "Observation":
        if self.knowledge_class not in _ALLOWED_OBSERVATION_CLASSES:
            raise ValueError(
                "an observation cannot be classified as "
                f"{self.knowledge_class}; allowed: "
                f"{sorted(c.value for c in _ALLOWED_OBSERVATION_CLASSES)}"
            )
        return self
