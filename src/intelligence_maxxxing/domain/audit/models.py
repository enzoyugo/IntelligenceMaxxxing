"""AuditRecord and EngineEvent: the append-only backbone of the Engine.

Constitutional grounding:
- Governance §7: every material action must be reconstructable.
- Technical Architecture §8: material events are append-only.
- Constitution Law 1: no conclusion exists without traceable evidence.

Stage 1 additions:
- every event/audit is scoped by tenant/owner/application (logical isolation);
- events carry an integrity hash chain per (owner, application) stream;
- audit health_state stores a real measured HealthSnapshot, never a literal.
"""

from pydantic import Field

from intelligence_maxxxing.domain.common.base import (
    DomainModel,
    SchemaVersion,
    UtcDatetime,
)
from intelligence_maxxxing.domain.common.epistemic import ActorType


class Actor(DomainModel):
    """Who performed an action against the Engine.

    Stage 1: always resolved from the authenticated context, never from a
    request body.
    """

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
    tenant_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    application_id: str = Field(min_length=1)
    actor: Actor
    schema_version: SchemaVersion
    payload: dict[str, object]
    occurred_at: UtcDatetime
    recorded_at: UtcDatetime
    audit_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    idempotency_key: str | None = None
    # Integrity chain per (owner_id, application_id) stream. Computed by the
    # event store at append time; None only before persistence or for
    # pre-Stage-1 legacy rows.
    previous_event_hash: str | None = None
    event_hash: str | None = None
    # Assigned by the database at append time (monotonic global order).
    global_position: int | None = None


class AuditRecord(DomainModel):
    """A recoverable record of what happened, sufficient without console logs."""

    audit_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    engine_version: str = Field(min_length=1)
    api_version: str = Field(min_length=1)
    schema_version: SchemaVersion
    domain_pack: str = Field(default="core", min_length=1)
    tenant_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    application_id: str = Field(min_length=1)
    actor: Actor
    action: str = Field(min_length=1)
    input_object_ids: tuple[str, ...] = ()
    output_object_ids: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()
    timestamp: UtcDatetime
    # Serialized HealthSnapshot: measured components, unchecked components and
    # the snapshot timestamp. Never a hardcoded "everything healthy" literal.
    health_state: dict[str, object] = Field(default_factory=dict)
