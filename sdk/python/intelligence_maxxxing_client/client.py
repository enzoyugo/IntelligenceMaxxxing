"""HTTP client for the IntelligenceMaxxxing Engine public API v1."""

import uuid
from datetime import datetime
from typing import Any

import httpx

from intelligence_maxxxing_client.errors import (
    EngineAPIError,
    EngineConflictError,
    EngineNotFoundError,
    EngineUnavailableError,
    EngineValidationError,
)
from intelligence_maxxxing_client.models import (
    AuditView,
    EnvelopeMeta,
    HealthView,
    ObservationAcceptedView,
)

_ERROR_BY_STATUS: dict[int, type[EngineAPIError]] = {
    404: EngineNotFoundError,
    409: EngineConflictError,
    422: EngineValidationError,
}


def new_idempotency_key() -> str:
    """Generate a client-side idempotency key for a new logical submission."""
    return f"idem_{uuid.uuid4().hex}"


class IntelligenceMaxxxingClient:
    """Small typed client. Consumes public HTTP contracts only.

    Can be constructed with an explicit httpx client (e.g. an ASGI transport
    in tests); otherwise it creates a real HTTP client with a timeout.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8100",
        timeout_seconds: float = 10.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> "IntelligenceMaxxxingClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self._http.request(method, path, json=json_body, headers=headers)
        except httpx.HTTPError as exc:
            raise EngineUnavailableError(f"engine unreachable: {type(exc).__name__}") from exc

        try:
            envelope: dict[str, Any] = response.json()
        except ValueError as exc:
            raise EngineAPIError(
                code="INVALID_RESPONSE",
                message="engine returned a non-JSON response",
                status_code=response.status_code,
            ) from exc

        if not envelope.get("ok", False):
            error = envelope.get("error") or {}
            meta = envelope.get("meta") or {}
            error_cls = _ERROR_BY_STATUS.get(response.status_code, EngineAPIError)
            raise error_cls(
                code=str(error.get("code", "UNKNOWN_ERROR")),
                message=str(error.get("message", "unknown engine error")),
                status_code=response.status_code,
                details=error.get("details") or {},
                request_id=meta.get("request_id"),
            )
        return envelope

    def health(self) -> HealthView:
        envelope = self._request("GET", "/api/v1/health")
        data = envelope["data"]
        return HealthView(**data, meta=EnvelopeMeta(**envelope["meta"]))

    def submit_observation(
        self,
        *,
        subject: str,
        statement: str,
        knowledge_class: str,
        observed_by: str,
        scope: str,
        idempotency_key: str,
        schema_version: str = "1.0",
        domain_pack: str = "core",
        unknown_reason: str | None = None,
        occurred_at: datetime | None = None,
        source_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        context_attributes: dict[str, Any] | None = None,
    ) -> ObservationAcceptedView:
        body: dict[str, Any] = {
            "schema_version": schema_version,
            "domain_pack": domain_pack,
            "subject": subject,
            "statement": statement,
            "knowledge_class": knowledge_class,
            "observed_by": observed_by,
            "context": {"scope": scope, "attributes": context_attributes or {}},
            "source_ids": source_ids or [],
            "metadata": metadata or {},
        }
        if unknown_reason is not None:
            body["unknown_reason"] = unknown_reason
        if occurred_at is not None:
            body["occurred_at"] = occurred_at.isoformat()

        envelope = self._request(
            "POST",
            "/api/v1/observations",
            json_body=body,
            headers={"Idempotency-Key": idempotency_key},
        )
        return ObservationAcceptedView(**envelope["data"], meta=EnvelopeMeta(**envelope["meta"]))

    def get_audit(self, audit_id: str) -> AuditView:
        envelope = self._request("GET", f"/api/v1/audits/{audit_id}")
        return AuditView(**envelope["data"], meta=EnvelopeMeta(**envelope["meta"]))
