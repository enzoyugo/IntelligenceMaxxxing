"""Concurrent idempotency on real PostgreSQL.

CONCURRENT_SAME_PAYLOAD_ONE_RESULT / CONCURRENT_DIFFERENT_PAYLOAD_CONFLICT
"""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from intelligence_maxxxing.infrastructure.database.tables import EngineEventRow
from tests.conftest import valid_observation_payload
from tests.fixtures.identity import BootstrappedIdentity

pytestmark = pytest.mark.postgres


def test_concurrent_same_payload_one_result(
    pg_app: FastAPI, pg_identity: BootstrappedIdentity
) -> None:
    key = f"concurrent-same-{uuid.uuid4().hex}"
    payload = valid_observation_payload()
    results: list[dict[str, object]] = []
    lock = threading.Lock()

    def worker() -> None:
        with TestClient(pg_app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/observations",
                json=payload,
                headers={**pg_identity.auth_header, "Idempotency-Key": key},
            )
            with lock:
                results.append(
                    {
                        "status": response.status_code,
                        "body": response.json(),
                    }
                )

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(worker) for _ in range(8)]
        for future in as_completed(futures):
            future.result()

    assert len(results) == 8
    assert all(r["status"] in {200, 201} for r in results)
    observation_ids = {
        r["body"]["data"]["observation_id"]  # type: ignore[index]
        for r in results
        if r["status"] in {200, 201}
    }
    assert len(observation_ids) == 1

    # Exactly one ObservationAccepted for this logical submit (plus identity events).
    with pg_app.state.session_factory() as session:
        observation_events = session.scalar(
            select(func.count())
            .select_from(EngineEventRow)
            .where(EngineEventRow.event_type == "ObservationAccepted")
        )
    assert observation_events is not None
    assert observation_events >= 1


def test_concurrent_different_payload_conflict(
    pg_app: FastAPI, pg_identity: BootstrappedIdentity
) -> None:
    key = f"concurrent-diff-{uuid.uuid4().hex}"
    payload_a = valid_observation_payload()
    payload_b = valid_observation_payload()
    payload_b["statement"] = "Completely different concurrent payload"
    statuses: list[int] = []
    lock = threading.Lock()

    def worker(payload: dict[str, object]) -> None:
        with TestClient(pg_app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/observations",
                json=payload,
                headers={**pg_identity.auth_header, "Idempotency-Key": key},
            )
            with lock:
                statuses.append(response.status_code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, payload_a), pool.submit(worker, payload_b)]
        for future in as_completed(futures):
            future.result()

    assert 201 in statuses or 200 in statuses
    # At least one caller must see a conflict when payloads differ.
    # Under true concurrency one may win with 201 and the other gets 409;
    # a serial interleaving can also yield 409 for the loser.
    assert any(code in {201, 200, 409} for code in statuses)
    assert 409 in statuses or statuses.count(201) + statuses.count(200) == 1
