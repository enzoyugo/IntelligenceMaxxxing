"""Integration tests for the Stage 0 smoke path over the public API."""

import uuid

from fastapi.testclient import TestClient

from tests.conftest import valid_observation_payload


def _submit(client: TestClient, payload: dict[str, object], key: str) -> object:
    return client.post(
        "/api/v1/observations",
        json=payload,
        headers={"Idempotency-Key": key},
    )


class TestHealth:
    def test_authenticated_health_with_database(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"]["service"] == "IntelligenceMaxxxing Engine"
        assert body["data"]["engine_version"] == "0.1.0"
        assert body["data"]["constitution_version"] == "1.1"
        assert body["meta"]["health"]["database"] == "HEALTHY"
        assert body["meta"]["request_id"].startswith("req_")

    def test_live_remains_ok_when_database_unavailable(self, broken_db_app: object) -> None:
        with TestClient(broken_db_app, raise_server_exceptions=False) as client:  # type: ignore[arg-type]
            response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_ready_fails_when_database_unavailable(self, broken_db_app: object) -> None:
        with TestClient(broken_db_app, raise_server_exceptions=False) as client:  # type: ignore[arg-type]
            response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"

    def test_detailed_health_requires_auth(self, app: object) -> None:
        with TestClient(app, raise_server_exceptions=False) as client:  # type: ignore[arg-type]
            response = client.get("/api/v1/health")
        assert response.status_code == 401


class TestSubmitObservation:
    def test_valid_observation_returns_201(self, client: TestClient) -> None:
        response = _submit(client, valid_observation_payload(), f"key-{uuid.uuid4().hex}")
        assert response.status_code == 201
        body = response.json()
        assert body["ok"] is True
        assert body["data"]["observation_id"].startswith("obs_")
        assert body["data"]["event_id"].startswith("evt_")
        assert body["data"]["audit_id"].startswith("aud_")
        assert body["data"]["replayed"] is False
        assert body["meta"]["audit_id"] == body["data"]["audit_id"]

    def test_invalid_observation_returns_typed_error(self, client: TestClient) -> None:
        payload = valid_observation_payload()
        payload["knowledge_class"] = "INFERENCE"
        response = _submit(client, payload, f"key-{uuid.uuid4().hex}")
        assert response.status_code == 422
        body = response.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_extra_field_is_rejected(self, client: TestClient) -> None:
        payload = valid_observation_payload()
        payload["belief_override"] = "not allowed"
        response = _submit(client, payload, f"key-{uuid.uuid4().hex}")
        assert response.status_code == 422

    def test_missing_idempotency_key_fails(self, client: TestClient) -> None:
        response = client.post("/api/v1/observations", json=valid_observation_payload())
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_missing_schema_version_fails(self, client: TestClient) -> None:
        payload = valid_observation_payload()
        del payload["schema_version"]
        response = _submit(client, payload, f"key-{uuid.uuid4().hex}")
        assert response.status_code == 422

    def test_unknown_without_reason_fails(self, client: TestClient) -> None:
        payload = valid_observation_payload()
        payload["knowledge_class"] = "UNKNOWN"
        response = _submit(client, payload, f"key-{uuid.uuid4().hex}")
        assert response.status_code == 422


class TestIdempotency:
    def test_retry_same_payload_returns_original(self, client: TestClient) -> None:
        key = f"key-{uuid.uuid4().hex}"
        payload = valid_observation_payload()

        first = _submit(client, payload, key)
        retry = _submit(client, payload, key)

        assert first.status_code == 201
        assert retry.status_code == 200
        assert retry.json()["data"]["replayed"] is True
        assert retry.json()["data"]["observation_id"] == first.json()["data"]["observation_id"]
        assert retry.json()["data"]["event_id"] == first.json()["data"]["event_id"]
        assert retry.json()["data"]["audit_id"] == first.json()["data"]["audit_id"]

    def test_retry_different_payload_returns_409(self, client: TestClient) -> None:
        key = f"key-{uuid.uuid4().hex}"
        first = _submit(client, valid_observation_payload(), key)
        assert first.status_code == 201

        changed = valid_observation_payload()
        changed["statement"] = "Slept 2 hours"
        conflict = _submit(client, changed, key)

        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


class TestAudit:
    def test_audit_is_recoverable(self, client: TestClient) -> None:
        submitted = _submit(client, valid_observation_payload(), f"key-{uuid.uuid4().hex}")
        audit_id = submitted.json()["data"]["audit_id"]

        response = client.get(f"/api/v1/audits/{audit_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"]["audit_id"] == audit_id
        assert body["data"]["action"] == "observations.submit"
        assert body["data"]["output_object_ids"] == [submitted.json()["data"]["observation_id"]]
        assert body["data"]["event_ids"] == [submitted.json()["data"]["event_id"]]
        assert len(body["data"]["events"]) == 1
        event = body["data"]["events"][0]
        assert event["event_type"] == "ObservationAccepted"
        assert event["payload"]["statement"] == "Slept 7.5 hours"

    def test_unknown_audit_id_returns_404(self, client: TestClient) -> None:
        response = client.get("/api/v1/audits/aud_doesnotexist")
        assert response.status_code == 404
        body = response.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "AUDIT_NOT_FOUND"


class TestEventPersistence:
    def test_event_preserves_timestamps_and_schema_version(self, client: TestClient) -> None:
        payload = valid_observation_payload()
        payload["occurred_at"] = "2026-07-18T22:00:00+00:00"
        submitted = _submit(client, payload, f"key-{uuid.uuid4().hex}")
        audit_id = submitted.json()["data"]["audit_id"]

        audit = client.get(f"/api/v1/audits/{audit_id}").json()
        event = audit["data"]["events"][0]
        assert event["schema_version"] == "1.0"
        assert event["occurred_at"].startswith("2026-07-18T22:00:00")
        assert event["recorded_at"]
        assert event["payload"]["schema_version"] == "1.0"
