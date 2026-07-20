"""HTTP client for the IntelligenceMaxxxing Engine public API v1 (Stage 1 auth)."""

import uuid
from datetime import datetime
from typing import Any

import httpx

from intelligence_maxxxing_client.errors import (
    EngineAPIError,
    EngineConflictError,
    EngineForbiddenError,
    EngineNotFoundError,
    EngineServiceUnavailableError,
    EngineUnauthorizedError,
    EngineUnavailableError,
    EngineValidationError,
)
from intelligence_maxxxing_client.models import (
    AuditView,
    BeliefListView,
    BeliefView,
    EnvelopeMeta,
    EvaluateExperimentResult,
    ExperimentProgressView,
    ExperimentView,
    HealthView,
    HypothesisListView,
    HypothesisParameters,
    HypothesisView,
    HypothesisWriteResult,
    LearningListView,
    LearningView,
    ObservationAcceptedView,
    ObservationListView,
    ObservationView,
)

_ERROR_BY_STATUS: dict[int, type[EngineAPIError]] = {
    401: EngineUnauthorizedError,
    403: EngineForbiddenError,
    404: EngineNotFoundError,
    409: EngineConflictError,
    422: EngineValidationError,
    503: EngineServiceUnavailableError,
}


def new_idempotency_key() -> str:
    """Generate a client-side idempotency key for a new logical submission."""
    return f"idem_{uuid.uuid4().hex}"


class IntelligenceMaxxxingClient:
    """Small typed client. Consumes public HTTP contracts only.

    Stage 1: every call (except /health/live and /health/ready) requires a
    Bearer credential. The secret is never logged by this client.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8100",
        *,
        credential_secret: str | None = None,
        timeout_seconds: float = 10.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._owns_client = http_client is None
        self._credential_secret = credential_secret
        self._http = http_client or httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> "IntelligenceMaxxxingClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _auth_headers(self) -> dict[str, str]:
        if not self._credential_secret:
            return {}
        return {"Authorization": f"Bearer {self._credential_secret}"}

    def _request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        merged = {**self._auth_headers(), **(headers or {})}
        try:
            response = self._http.request(
                method, path, json=json_body, headers=merged, params=params
            )
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

    def live(self) -> dict[str, str]:
        """Public liveness probe (no auth)."""
        try:
            response = self._http.get("/health/live")
            response.raise_for_status()
            return dict(response.json())
        except httpx.HTTPError as exc:
            raise EngineUnavailableError(f"engine unreachable: {type(exc).__name__}") from exc

    def ready(self) -> dict[str, str]:
        """Public readiness probe (no auth). Raises EngineServiceUnavailableError on 503."""
        try:
            response = self._http.get("/health/ready")
        except httpx.HTTPError as exc:
            raise EngineUnavailableError(f"engine unreachable: {type(exc).__name__}") from exc
        if response.status_code == 503:
            raise EngineServiceUnavailableError(
                code="NOT_READY",
                message="engine is not ready",
                status_code=503,
            )
        return dict(response.json())

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

    def get_observation(self, observation_id: str) -> ObservationView:
        envelope = self._request("GET", f"/api/v1/observations/{observation_id}")
        return ObservationView(**envelope["data"])

    def list_observations(
        self,
        *,
        domain_pack: str | None = None,
        cursor: int | None = None,
        limit: int = 50,
    ) -> ObservationListView:
        params: dict[str, Any] = {"limit": limit}
        if domain_pack is not None:
            params["domain_pack"] = domain_pack
        if cursor is not None:
            params["cursor"] = cursor
        envelope = self._request("GET", "/api/v1/observations", params=params)
        data = envelope["data"]
        return ObservationListView(
            items=[ObservationView(**item) for item in data.get("items", [])],
            next_cursor=data.get("next_cursor"),
            projection_name=data["projection_name"],
            projection_version=data["projection_version"],
            projection_position=data.get("projection_position"),
            projection_updated_at=data.get("projection_updated_at"),
            meta=EnvelopeMeta(**envelope["meta"]),
        )

    def get_audit(self, audit_id: str) -> AuditView:
        envelope = self._request("GET", f"/api/v1/audits/{audit_id}")
        return AuditView(**envelope["data"], meta=EnvelopeMeta(**envelope["meta"]))

    def create_hypothesis(
        self,
        *,
        idempotency_key: str,
        parameters: dict[str, Any] | HypothesisParameters | None = None,
        human_confirmed: bool = False,
    ) -> HypothesisWriteResult:
        body: dict[str, Any] = {"human_confirmed": human_confirmed}
        if parameters is not None:
            if isinstance(parameters, HypothesisParameters):
                body["parameters"] = parameters.model_dump()
            else:
                body["parameters"] = parameters
        envelope = self._request(
            "POST",
            "/api/v1/hypotheses",
            json_body=body,
            headers={"Idempotency-Key": idempotency_key},
        )
        return HypothesisWriteResult(**envelope["data"], meta=EnvelopeMeta(**envelope["meta"]))

    def list_hypotheses(self) -> HypothesisListView:
        envelope = self._request("GET", "/api/v1/hypotheses")
        data = envelope["data"] or {}
        return HypothesisListView(
            items=[HypothesisView(**item) for item in data.get("items", [])],
            meta=EnvelopeMeta(**envelope["meta"]),
        )

    def get_hypothesis(self, hypothesis_id: str) -> HypothesisView:
        envelope = self._request("GET", f"/api/v1/hypotheses/{hypothesis_id}")
        return HypothesisView(**envelope["data"])

    def activate_hypothesis(
        self,
        hypothesis_id: str,
        *,
        parameters: dict[str, Any] | HypothesisParameters,
        idempotency_key: str,
    ) -> HypothesisWriteResult:
        payload = (
            parameters.model_dump() if isinstance(parameters, HypothesisParameters) else parameters
        )
        envelope = self._request(
            "POST",
            f"/api/v1/hypotheses/{hypothesis_id}/activate",
            json_body={"parameters": payload},
            headers={"Idempotency-Key": idempotency_key},
        )
        return HypothesisWriteResult(**envelope["data"], meta=EnvelopeMeta(**envelope["meta"]))

    def retire_hypothesis(
        self,
        hypothesis_id: str,
        *,
        reason: str,
        idempotency_key: str,
    ) -> HypothesisWriteResult:
        envelope = self._request(
            "POST",
            f"/api/v1/hypotheses/{hypothesis_id}/retire",
            json_body={"reason": reason},
            headers={"Idempotency-Key": idempotency_key},
        )
        return HypothesisWriteResult(**envelope["data"], meta=EnvelopeMeta(**envelope["meta"]))

    def get_experiment(self, experiment_id: str) -> ExperimentView:
        envelope = self._request("GET", f"/api/v1/experiments/{experiment_id}")
        return ExperimentView(**envelope["data"])

    def get_experiment_progress(self, experiment_id: str) -> ExperimentProgressView:
        envelope = self._request("GET", f"/api/v1/experiments/{experiment_id}/progress")
        return ExperimentProgressView(**envelope["data"])

    def evaluate_experiment(
        self,
        experiment_id: str,
        *,
        phase: str,
        idempotency_key: str,
    ) -> EvaluateExperimentResult:
        envelope = self._request(
            "POST",
            f"/api/v1/experiments/{experiment_id}/evaluate",
            json_body={"phase": phase},
            headers={"Idempotency-Key": idempotency_key},
        )
        return EvaluateExperimentResult(**envelope["data"], meta=EnvelopeMeta(**envelope["meta"]))

    def get_current_belief(self, hypothesis_id: str) -> BeliefView | None:
        envelope = self._request("GET", f"/api/v1/hypotheses/{hypothesis_id}/beliefs/current")
        data = envelope.get("data")
        if data is None:
            return None
        return BeliefView(**data)

    def list_beliefs(self, hypothesis_id: str) -> BeliefListView:
        envelope = self._request("GET", f"/api/v1/hypotheses/{hypothesis_id}/beliefs")
        data = envelope["data"] or {}
        return BeliefListView(
            items=[BeliefView(**item) for item in data.get("items", [])],
            meta=EnvelopeMeta(**envelope["meta"]),
        )

    def list_learning(self, hypothesis_id: str) -> LearningListView:
        envelope = self._request("GET", f"/api/v1/hypotheses/{hypothesis_id}/learning")
        data = envelope["data"] or {}
        return LearningListView(
            items=[LearningView(**item) for item in data.get("items", [])],
            meta=EnvelopeMeta(**envelope["meta"]),
        )

    def get_wellbeing_current(self, *, window_days: int = 14) -> dict[str, Any]:
        envelope = self._request(
            "GET",
            "/api/v1/wellbeing/current",
            params={"window_days": window_days},
        )
        return envelope["data"] or {}

    def get_wellbeing_history(self, *, limit: int = 20) -> dict[str, Any]:
        envelope = self._request(
            "GET",
            "/api/v1/wellbeing/history",
            params={"limit": limit},
        )
        return envelope["data"] or {}

    def get_wellbeing_explanation(
        self, *, score_snapshot_id: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if score_snapshot_id:
            params["score_snapshot_id"] = score_snapshot_id
        envelope = self._request("GET", "/api/v1/wellbeing/explanation", params=params or None)
        return envelope["data"] or {}

    def get_wellbeing_formula(self) -> dict[str, Any]:
        envelope = self._request("GET", "/api/v1/wellbeing/formula")
        return envelope["data"] or {}

    def submit_wellbeing_feedback(
        self,
        *,
        rating: str,
        score_snapshot_id: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"rating": rating}
        if score_snapshot_id is not None:
            body["score_snapshot_id"] = score_snapshot_id
        if note is not None:
            body["note"] = note
        envelope = self._request("POST", "/api/v1/wellbeing/feedback", json_body=body)
        return envelope["data"] or {}
