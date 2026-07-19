"""Idempotency protections (Engine Service Contract §11).

IDEMPOTENT_RETRY_DOES_NOT_DUPLICATE / IDEMPOTENCY_PAYLOAD_CONFLICT_REJECTED
"""

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from intelligence_maxxxing.infrastructure.database.tables import (
    AuditRecordRow,
    EngineEventRow,
)
from tests.conftest import valid_observation_payload


def _count_rows(app: FastAPI) -> tuple[int, int]:
    factory = app.state.session_factory
    with factory() as session:
        events = session.scalar(select(func.count()).select_from(EngineEventRow)) or 0
        audits = session.scalar(select(func.count()).select_from(AuditRecordRow)) or 0
    return events, audits


def test_idempotent_retry_does_not_duplicate(app: FastAPI, client: TestClient) -> None:
    key = f"key-{uuid.uuid4().hex}"
    payload = valid_observation_payload()

    first = client.post("/api/v1/observations", json=payload, headers={"Idempotency-Key": key})
    assert first.status_code == 201
    events_after_first, audits_after_first = _count_rows(app)

    for _ in range(3):
        retry = client.post("/api/v1/observations", json=payload, headers={"Idempotency-Key": key})
        assert retry.status_code == 200
        assert retry.json()["data"]["replayed"] is True

    events_after_retries, audits_after_retries = _count_rows(app)
    assert events_after_retries == events_after_first, "retries must not duplicate events"
    assert audits_after_retries == audits_after_first, "retries must not duplicate audits"


def test_idempotency_payload_conflict_rejected(app: FastAPI, client: TestClient) -> None:
    key = f"key-{uuid.uuid4().hex}"
    original = valid_observation_payload()
    client.post("/api/v1/observations", json=original, headers={"Idempotency-Key": key})
    events_before, _ = _count_rows(app)

    tampered = valid_observation_payload()
    tampered["statement"] = "completely different statement"
    conflict = client.post("/api/v1/observations", json=tampered, headers={"Idempotency-Key": key})

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    events_after, _ = _count_rows(app)
    assert events_after == events_before, "a rejected conflict must not create events"
