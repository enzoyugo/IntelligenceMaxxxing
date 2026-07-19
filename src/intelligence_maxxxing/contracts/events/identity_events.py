"""Payload schemas for identity and permission events (Stage 1)."""

from pydantic import BaseModel, ConfigDict, Field

from intelligence_maxxxing.domain.common.base import SchemaVersion, UtcDatetime


class _EventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ApplicationRegisteredPayload(_EventPayload):
    application_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    schema_version: SchemaVersion
    registered_at: UtcDatetime


class ApplicationCredentialCreatedPayload(_EventPayload):
    # Never contains the secret or its hash: only public metadata.
    credential_id: str = Field(min_length=1)
    application_id: str = Field(min_length=1)
    created_at: UtcDatetime
    expires_at: UtcDatetime | None = None


class ApplicationCredentialRotatedPayload(_EventPayload):
    old_credential_id: str = Field(min_length=1)
    new_credential_id: str = Field(min_length=1)
    application_id: str = Field(min_length=1)
    rotated_at: UtcDatetime


class ApplicationCredentialRevokedPayload(_EventPayload):
    credential_id: str = Field(min_length=1)
    application_id: str = Field(min_length=1)
    revoked_at: UtcDatetime


class UserRegisteredPayload(_EventPayload):
    user_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    registered_at: UtcDatetime


class PermissionGrantedPayload(_EventPayload):
    application_id: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    granted_at: UtcDatetime


class PermissionRevokedPayload(_EventPayload):
    application_id: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    revoked_at: UtcDatetime
