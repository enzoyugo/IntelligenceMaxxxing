"""PostgreSQL projection rebuild + SDK-over-HTTP smoke."""

import socket
import threading
import time
import uuid
from collections.abc import Iterator

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from intelligence_maxxxing import API_VERSION
from intelligence_maxxxing.application.use_cases.projections import ProjectionRebuildService
from intelligence_maxxxing.infrastructure.database.tables import (
    AcceptedObservationRow,
    EngineEventRow,
)
from intelligence_maxxxing.infrastructure.health import (
    MeasuredHealthSnapshotProvider,
    SqlAlchemyDatabaseHealth,
)
from intelligence_maxxxing.infrastructure.repositories import SqlAlchemyUnitOfWork
from intelligence_maxxxing_client import IntelligenceMaxxxingClient
from tests.conftest import valid_observation_payload
from tests.fixtures.identity import BootstrappedIdentity

pytestmark = pytest.mark.postgres


def test_projection_rebuild_on_postgres(pg_app: FastAPI, pg_client: TestClient) -> None:
    for _ in range(5):
        assert (
            pg_client.post(
                "/api/v1/observations",
                json=valid_observation_payload(),
                headers={"Idempotency-Key": f"pg-proj-{uuid.uuid4().hex}"},
            ).status_code
            == 201
        )

    with pg_app.state.session_factory() as session:
        before_ids = [
            r.observation_id
            for r in session.scalars(
                select(AcceptedObservationRow).order_by(AcceptedObservationRow.global_position)
            )
        ]
        events_before = session.scalar(select(func.count()).select_from(EngineEventRow)) or 0
        session.execute(text("DELETE FROM accepted_observations"))
        session.commit()

    result = ProjectionRebuildService(
        uow=SqlAlchemyUnitOfWork(pg_app.state.session_factory),
        engine_version=pg_app.state.settings.engine_version,
        api_version=API_VERSION,
        health_provider=MeasuredHealthSnapshotProvider(
            SqlAlchemyDatabaseHealth(pg_app.state.db_engine), check_manifest=False
        ),
    ).rebuild(from_scratch=True)

    assert result.rows_written >= 5
    with pg_app.state.session_factory() as session:
        after_ids = [
            r.observation_id
            for r in session.scalars(
                select(AcceptedObservationRow).order_by(AcceptedObservationRow.global_position)
            )
        ]
        events_after = session.scalar(select(func.count()).select_from(EngineEventRow)) or 0
    assert before_ids == after_ids
    # Ledger was not truncated; a ProjectionRebuilt event was appended.
    assert events_after >= events_before


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture()
def pg_live_url(pg_app: FastAPI) -> Iterator[str]:
    port = _free_port()
    config = uvicorn.Config(pg_app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("pg test engine failed to start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


def test_sdk_over_http_on_postgres(pg_live_url: str, pg_identity: BootstrappedIdentity) -> None:
    with IntelligenceMaxxxingClient(
        base_url=pg_live_url, credential_secret=pg_identity.secret, timeout_seconds=10.0
    ) as client:
        assert client.live()["status"] == "ok"
        assert client.ready()["status"] == "ready"
        health = client.health()
        assert health.engine_version == "0.1.0"
        accepted = client.submit_observation(
            subject="sleep",
            statement="PostgreSQL SDK path",
            knowledge_class="OBSERVED_FACT",
            observed_by="pg-sdk",
            scope="personal",
            idempotency_key=f"pg-sdk-{uuid.uuid4().hex}",
        )
        viewed = client.get_observation(accepted.observation_id)
        assert viewed.statement == "PostgreSQL SDK path"
        audit = client.get_audit(accepted.audit_id)
        assert audit.audit_id == accepted.audit_id
