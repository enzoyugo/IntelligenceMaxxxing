"""Payload schemas for projection and integrity governance events (Stage 1)."""

from pydantic import BaseModel, ConfigDict, Field

from intelligence_maxxxing.domain.common.base import UtcDatetime


class _EventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProjectionRebuiltPayload(_EventPayload):
    projection_name: str = Field(min_length=1)
    projection_version: str = Field(min_length=1)
    events_applied: int = Field(ge=0)
    rows_written: int = Field(ge=0)
    last_global_position: int = Field(ge=0)
    checksum: str | None = None
    rebuilt_at: UtcDatetime


class ProjectionCheckpointCreatedPayload(_EventPayload):
    projection_name: str = Field(min_length=1)
    projection_version: str = Field(min_length=1)
    last_global_position: int = Field(ge=0)
    created_at: UtcDatetime


class IntegrityCheckCompletedPayload(_EventPayload):
    streams_checked: int = Field(ge=0)
    events_checked: int = Field(ge=0)
    violations_found: int = Field(ge=0)
    mode: str = Field(min_length=1, description="FULL or INCREMENTAL")
    completed_at: UtcDatetime


class IntegrityViolationDetectedPayload(_EventPayload):
    stream_owner_id: str = Field(min_length=1)
    stream_application_id: str = Field(min_length=1)
    broken_event_id: str = Field(min_length=1)
    detected_at: UtcDatetime


class IntegrityStreamQuarantinedPayload(_EventPayload):
    stream_tenant_id: str = Field(min_length=1)
    stream_owner_id: str = Field(min_length=1)
    stream_application_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    broken_event_id: str = Field(min_length=1)
    detected_at: UtcDatetime


class IntegrityStreamVerifiedPayload(_EventPayload):
    stream_tenant_id: str = Field(min_length=1)
    stream_owner_id: str = Field(min_length=1)
    stream_application_id: str = Field(min_length=1)
    events_checked: int = Field(ge=0)
    verified_at: UtcDatetime


class IntegrityStreamReleasedPayload(_EventPayload):
    stream_tenant_id: str = Field(min_length=1)
    stream_owner_id: str = Field(min_length=1)
    stream_application_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    released_by: str = Field(min_length=1)
    released_at: UtcDatetime
