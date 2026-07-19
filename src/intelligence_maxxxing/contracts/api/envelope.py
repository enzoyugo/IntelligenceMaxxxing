"""Versioned response envelope (Engine Service Contract §8)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorInfo(BaseModel):
    """Typed error surfaced to clients. Never contains stack traces or secrets."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    engine_version: str
    api_version: str = "v1"
    domain_pack: str = "core"
    domain_pack_version: str | None = None
    generated_at: str
    freshness: dict[str, Any] = Field(default_factory=dict)
    confidence: dict[str, Any] | None = None
    health: dict[str, str] = Field(default_factory=dict)
    audit_id: str | None = None


class ApiResponseEnvelope(BaseModel):
    """Every public API response uses this envelope."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    data: dict[str, Any] | None = None
    error: ErrorInfo | None = None
    meta: ResponseMeta
