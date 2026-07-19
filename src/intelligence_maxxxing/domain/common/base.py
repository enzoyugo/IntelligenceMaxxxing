"""Base contracts for canonical domain objects.

Constitutional grounding:
- Constitution Art. 5/6: every assertion carries confidence, evidence, context.
- Constitution Art. 34 / Law 9: original records are immutable (frozen models).
- Epistemic Standard §12: required epistemic object fields.
"""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
)

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"
CANONICAL_SCHEMA_VERSION = "1.0"

_METADATA_MAX_KEYS = 32
_METADATA_MAX_KEY_LENGTH = 64
_METADATA_MAX_TEXT_LENGTH = 2000

MetadataValue = str | int | float | bool | None


def utc_now() -> datetime:
    """Current UTC timestamp. The only time source domain objects should use."""
    return datetime.now(UTC)


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware (UTC)")
    return value.astimezone(UTC)


def _validate_metadata(value: dict[str, MetadataValue]) -> dict[str, MetadataValue]:
    if len(value) > _METADATA_MAX_KEYS:
        raise ValueError(f"metadata cannot exceed {_METADATA_MAX_KEYS} keys")
    for key, item in value.items():
        if len(key) > _METADATA_MAX_KEY_LENGTH:
            raise ValueError(f"metadata key too long: {key[:80]!r}")
        if isinstance(item, str) and len(item) > _METADATA_MAX_TEXT_LENGTH:
            raise ValueError(f"metadata value too long for key {key!r}")
    return value


UtcDatetime = Annotated[datetime, AfterValidator(_require_utc)]

# Deliberately limited: metadata is an escape hatch for small controlled
# annotations, never a replacement for real schema design.
LimitedMetadata = Annotated[dict[str, MetadataValue], AfterValidator(_validate_metadata)]

SchemaVersion = Annotated[str, Field(pattern=SCHEMA_VERSION_PATTERN)]


class DomainModel(BaseModel):
    """Strict, immutable base for all canonical domain objects."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Context(DomainModel):
    """Mandatory context and scope for knowledge objects (Epistemic Standard §2).

    Designed single-user first but with explicit user/tenant boundaries so a
    multiuser future does not require a rewrite (Technical Architecture §7).
    """

    schema_version: SchemaVersion = CANONICAL_SCHEMA_VERSION
    scope: str = Field(min_length=1, description="Scope in which the assertion applies")
    user_id: str | None = None
    tenant_id: str = Field(default="primary", min_length=1)
    environment: str | None = None
    attributes: LimitedMetadata = Field(default_factory=dict)


class CanonicalObject(DomainModel):
    """Common material-object fields (Stage 0 prompt §8, Epistemic Standard §12)."""

    id: str = Field(min_length=1)
    schema_version: SchemaVersion
    domain_pack: str = Field(default="core", min_length=1)
    subject: str = Field(min_length=1)
    context: Context
    created_at: UtcDatetime
    occurred_at: UtcDatetime | None = None
    source_ids: tuple[str, ...] = ()
    metadata: LimitedMetadata = Field(default_factory=dict)
