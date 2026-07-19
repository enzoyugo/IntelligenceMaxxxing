"""AuditRecord and EngineEvent: the append-only backbone of the Engine.

Constitutional grounding:
- Governance §7: every material action must be reconstructable.
- Technical Architecture §8: material events are append-only.
- Constitution Law 1: no conclusion exists without traceable evidence.
"""

from pydantic import Field

from intelligence_maxxxing.domain.common.base import (
    DomainModel,
    LimitedMetadata,
    SchemaVersion,
    UtcDatetime,
)
from intelligence_maxxxing.domain.common.epistemic import ActorType


class Actor(DomainModel):
    """Who performed an action against the Engine."""

    actor_type: ActorType
    actor_id: str = Field(min_length=1)


class EngineEvent(DomainModel):
    """An immutable, append-only event. There is no update and no delete."""

    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    aggregate_type: str = Field(min_length=1)
    aggregate_id: str = Field(min_length=1)
    aggregate_version: int = Field(ge=1)
    domain_pack: str = Field(default="core", min_length=1)
    actor: Actor
    schema_version: SchemaVersion
    payload: dict[str, object]
    occurred_at: UtcDatetime
    recorded_at: UtcDatetime
    audit_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    idempotency_key: str | None = None


class AuditRecord(DomainModel):
    """A recoverable record of what happened, sufficient without console logs."""

    audit_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    engine_version: str = Field(min_length=1)
    api_version: str = Field(min_length=1)
    schema_version: SchemaVersion
    domain_pack: str = Field(default="core", min_length=1)
    actor: Actor
    action: str = Field(min_length=1)
    input_object_ids: tuple[str, ...] = ()
    output_object_ids: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()
    timestamp: UtcDatetime
    health_state: LimitedMetadata = Field(default_factory=dict)
