"""Source contract with lineage fields (Epistemic Standard §8)."""

from pydantic import Field

from intelligence_maxxxing.domain.common.base import (
    CANONICAL_SCHEMA_VERSION,
    DomainModel,
    LimitedMetadata,
    SchemaVersion,
    UtcDatetime,
)
from intelligence_maxxxing.domain.common.epistemic import SourceType


class Source(DomainModel):
    """An identified origin of evidence. Dependent sources must not count twice."""

    id: str = Field(min_length=1)
    schema_version: SchemaVersion = CANONICAL_SCHEMA_VERSION
    name: str = Field(min_length=1)
    source_type: SourceType
    parent_source_id: str | None = None
    acquisition_method: str | None = None
    transformation_chain: tuple[str, ...] = ()
    suspected_common_dependency: str | None = None
    created_at: UtcDatetime
    metadata: LimitedMetadata = Field(default_factory=dict)
