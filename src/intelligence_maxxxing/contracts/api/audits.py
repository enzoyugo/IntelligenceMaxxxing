"""Public contract for GET /api/v1/audits/{audit_id}."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PublicEngineEvent(BaseModel):
    """Public projection of an engine event (internal rows are never exposed)."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int
    domain_pack: str
    schema_version: str
    payload: dict[str, Any]
    occurred_at: str
    recorded_at: str


class AuditRecordData(BaseModel):
    """Recoverable audit record; enough to reconstruct what happened."""

    model_config = ConfigDict(extra="forbid")

    audit_id: str
    request_id: str
    engine_version: str
    api_version: str
    schema_version: str
    domain_pack: str
    actor_type: str
    actor_id: str
    action: str
    input_object_ids: tuple[str, ...]
    output_object_ids: tuple[str, ...]
    event_ids: tuple[str, ...]
    timestamp: str
    health_state: dict[str, Any] = Field(default_factory=dict)
    events: tuple[PublicEngineEvent, ...] = ()
