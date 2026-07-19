"""Evidence contract (Constitution Art. 9; Epistemic Standard §5, §8).

Stage 0 status: CONTRACT_ONLY. The schema is binding; evaluation logic is not
implemented and is not simulated.
"""

from pydantic import Field

from intelligence_maxxxing.domain.common.knowledge import KnowledgeObject


class Evidence(KnowledgeObject):
    """A traceable piece of evidence supporting or weakening an assertion."""

    supports_object_ids: tuple[str, ...] = ()
    weakens_object_ids: tuple[str, ...] = ()
    methodology: str | None = None
    sample_description: str | None = None
    independence_notes: str | None = Field(
        default=None,
        description="Dependency on other sources; dependent evidence must not count twice",
    )
