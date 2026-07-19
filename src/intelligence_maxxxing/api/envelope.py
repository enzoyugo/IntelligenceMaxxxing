"""Helpers to build the versioned response envelope."""

from datetime import UTC, datetime
from typing import Any

from intelligence_maxxxing import API_VERSION
from intelligence_maxxxing.contracts.api.envelope import (
    ApiResponseEnvelope,
    ErrorInfo,
    ResponseMeta,
)


def build_meta(
    request_id: str,
    engine_version: str,
    *,
    domain_pack: str = "core",
    health: dict[str, str] | None = None,
    audit_id: str | None = None,
) -> ResponseMeta:
    return ResponseMeta(
        request_id=request_id,
        engine_version=engine_version,
        api_version=API_VERSION,
        domain_pack=domain_pack,
        generated_at=datetime.now(UTC).isoformat(),
        health=health or {},
        audit_id=audit_id,
    )


def success_envelope(data: dict[str, Any], meta: ResponseMeta) -> ApiResponseEnvelope:
    return ApiResponseEnvelope(ok=True, data=data, error=None, meta=meta)


def error_envelope(
    code: str,
    message: str,
    meta: ResponseMeta,
    details: dict[str, Any] | None = None,
) -> ApiResponseEnvelope:
    return ApiResponseEnvelope(
        ok=False,
        data=None,
        error=ErrorInfo(code=code, message=message, details=details or {}),
        meta=meta,
    )
