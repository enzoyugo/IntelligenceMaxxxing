"""Public SDK models mirroring the public API contract (not Core internals)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EnvelopeMeta(BaseModel):
    # Tolerant on input: the server may add meta fields within the same major version.
    model_config = ConfigDict(extra="ignore")

    request_id: str
    engine_version: str
    api_version: str
    domain_pack: str = "core"
    generated_at: str
    audit_id: str | None = None
    health: dict[str, str] = Field(default_factory=dict)


class HealthView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str
    service: str
    engine_version: str
    constitution_version: str
    meta: EnvelopeMeta


class ObservationAcceptedView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    observation_id: str
    event_id: str
    audit_id: str
    replayed: bool
    meta: EnvelopeMeta


class AuditEventView(BaseModel):
    model_config = ConfigDict(extra="ignore")

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


class AuditView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    audit_id: str
    request_id: str
    engine_version: str
    api_version: str
    schema_version: str
    domain_pack: str
    actor_type: str
    actor_id: str
    action: str
    input_object_ids: list[str]
    output_object_ids: list[str]
    event_ids: list[str]
    timestamp: str
    events: list[AuditEventView] = Field(default_factory=list)
    meta: EnvelopeMeta
