"""Canonical identity objects.

All identity objects are frozen and strict. The effective actor of any write
always comes from the authenticated context, never from a request body.
"""

from enum import StrEnum

from pydantic import Field

from intelligence_maxxxing.domain.common.base import (
    CANONICAL_SCHEMA_VERSION,
    DomainModel,
    LimitedMetadata,
    SchemaVersion,
    UtcDatetime,
)
from intelligence_maxxxing.domain.common.epistemic import ActorType


class IdentityStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class CredentialStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class _IdentityBase(DomainModel):
    id: str = Field(min_length=1)
    schema_version: SchemaVersion = CANONICAL_SCHEMA_VERSION
    status: IdentityStatus = IdentityStatus.ACTIVE
    display_name: str = Field(min_length=1)
    created_at: UtcDatetime
    disabled_at: UtcDatetime | None = None
    metadata: LimitedMetadata = Field(default_factory=dict)
    audit_id: str = Field(min_length=1)


class TenantIdentity(_IdentityBase):
    """A logical tenant. Initially the Constitutional Owner's private instance."""


class UserIdentity(_IdentityBase):
    """A human user (owner). Single-user today, multi-user capable by design."""

    tenant_id: str = Field(min_length=1)


class ApplicationIdentity(_IdentityBase):
    """An external application client (e.g. LifeMaxxxing in the future)."""

    tenant_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1, description="User that owns this application's data")


class ServiceIdentity(_IdentityBase):
    """An internal Engine service identity (projector, integrity checker, ...)."""

    tenant_id: str = Field(min_length=1)


class ActorIdentity(DomainModel):
    """The resolved, authenticated actor of an operation.

    Built exclusively from the authentication context; request bodies can
    never inject or override these fields.
    """

    actor_id: str = Field(min_length=1)
    actor_type: ActorType
    application_id: str | None = None
    owner_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
