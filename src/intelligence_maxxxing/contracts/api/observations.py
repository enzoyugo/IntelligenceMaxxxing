"""Public contract for POST /api/v1/observations."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from intelligence_maxxxing.domain.common.base import (
    Context,
    LimitedMetadata,
    SchemaVersion,
    UtcDatetime,
)
from intelligence_maxxxing.domain.common.epistemic import KnowledgeClass, UnknownReason

# Classes a client may submit as an observation. Inference and conclusion
# classes are produced only by governed Engine processes, never accepted raw.
SUBMITTABLE_KNOWLEDGE_CLASSES = frozenset(
    {
        KnowledgeClass.OBSERVED_FACT,
        KnowledgeClass.DERIVED_FACT,
        KnowledgeClass.HUMAN_VALUE,
        KnowledgeClass.UNKNOWN,
    }
)


class SubmitObservationRequest(BaseModel):
    """Strict public schema. Unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    schema_version: SchemaVersion = Field(description="Canonical schema version, e.g. '1.0'")
    domain_pack: str = Field(default="core", min_length=1)
    subject: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    knowledge_class: KnowledgeClass
    unknown_reason: UnknownReason | None = None
    observed_by: str = Field(min_length=1)
    context: Context
    occurred_at: UtcDatetime | None = None
    source_ids: tuple[str, ...] = ()
    metadata: LimitedMetadata = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_epistemic_rules(self) -> "SubmitObservationRequest":
        if self.knowledge_class not in SUBMITTABLE_KNOWLEDGE_CLASSES:
            raise ValueError(
                f"knowledge_class {self.knowledge_class} cannot be submitted as an "
                "observation; inferences and conclusions are produced only by "
                "governed Engine processes"
            )
        if self.knowledge_class is KnowledgeClass.UNKNOWN and self.unknown_reason is None:
            raise ValueError("UNKNOWN observations require unknown_reason")
        if self.knowledge_class is not KnowledgeClass.UNKNOWN and self.unknown_reason is not None:
            raise ValueError("unknown_reason is only valid when knowledge_class is UNKNOWN")
        return self


class ObservationAcceptedData(BaseModel):
    """Data section of a successful submission response."""

    model_config = ConfigDict(extra="forbid")

    observation_id: str
    event_id: str
    audit_id: str
    replayed: bool = Field(description="True when returned from an idempotent retry")
