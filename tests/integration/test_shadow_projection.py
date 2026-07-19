"""Non-destructive projection verify + atomic promote (Stage 1.1 §8).

VERIFY_DOES_NOT_MUTATE_LIVE_PROJECTION
VERIFY_FAILURE_PRESERVES_LIVE_PROJECTION
UNKNOWN_EVENT_IN_SHADOW_DOES_NOT_EMPTY_LIVE
SHADOW_CHECKSUM_MATCHES_LIVE
REBUILD_PROMOTION_IS_ATOMIC
FAILED_PROMOTION_ROLLS_BACK
READS_CONTINUE_DURING_VERIFY
"""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from intelligence_maxxxing import API_VERSION
from intelligence_maxxxing.application.errors import UnknownProjectionEventError
from intelligence_maxxxing.application.use_cases.projections import (
    ProjectionRebuildService,
    VerifyReport,
)
from intelligence_maxxxing.infrastructure.database.tables import (
    AcceptedObservationRow,
    AcceptedObservationShadowRow,
)
from intelligence_maxxxing.infrastructure.health import (
    MeasuredHealthSnapshotProvider,
    SqlAlchemyDatabaseHealth,
)
from intelligence_maxxxing.infrastructure.repositories import SqlAlchemyUnitOfWork
from tests.conftest import valid_observation_payload


def _service(app: FastAPI) -> ProjectionRebuildService:
    return ProjectionRebuildService(
        uow=SqlAlchemyUnitOfWork(app.state.session_factory),
        engine_version=app.state.settings.engine_version,
        api_version=API_VERSION,
        health_provider=MeasuredHealthSnapshotProvider(
            SqlAlchemyDatabaseHealth(app.state.db_engine), check_manifest=False
        ),
    )


def _submit_many(client: TestClient, n: int) -> None:
    for _ in range(n):
        response = client.post(
            "/api/v1/observations",
            json=valid_observation_payload(),
            headers={"Idempotency-Key": f"sh-{uuid.uuid4().hex}"},
        )
        assert response.status_code == 201


def _live_count(app: FastAPI) -> int:
    with app.state.session_factory() as session:
        return session.scalar(select(func.count()).select_from(AcceptedObservationRow)) or 0


def _inject_unknown_event(app: FastAPI) -> None:
    with app.state.session_factory() as session:
        session.execute(
            text(
                """
                INSERT INTO engine_events (
                    event_id, event_type, schema_version, aggregate_type, aggregate_id,
                    aggregate_version, domain_pack, tenant_id, owner_id, application_id,
                    actor_type, actor_id, payload, occurred_at, recorded_at, audit_id,
                    request_id
                ) VALUES (
                    'evt_unknown_shadow_test',
                    'TotallyUnknownForProjector',
                    '1.0', 'X', 'x1', 1, 'core',
                    'tnt_x', 'usr_x', 'app_x',
                    'SYSTEM', 'system', '{}',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP,
                    'aud_unknown_shadow_test', 'req_unknown_shadow_test'
                )
                """
            )
        )
        session.commit()


def test_verify_does_not_mutate_live_projection(app: FastAPI, client: TestClient) -> None:
    _submit_many(client, 3)
    before = _live_count(app)
    report = _service(app).verify()
    assert isinstance(report, VerifyReport)
    assert _live_count(app) == before
    # Shadow table is left clean after a verify.
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AcceptedObservationShadowRow)) == 0


def test_shadow_checksum_matches_live(app: FastAPI, client: TestClient) -> None:
    _submit_many(client, 2)
    report = _service(app).verify()
    assert report.matches is True
    assert report.ok is True
    assert report.shadow_checksum == report.live_checksum
    assert report.quarantined is False


def test_verify_failure_preserves_live_projection(app: FastAPI, client: TestClient) -> None:
    _submit_many(client, 3)
    before = _live_count(app)
    assert before == 3
    _inject_unknown_event(app)

    report = _service(app).verify()
    assert report.quarantined is True
    assert report.matches is False
    # Live is fully intact.
    assert _live_count(app) == before


def test_unknown_event_in_shadow_does_not_empty_live(app: FastAPI, client: TestClient) -> None:
    _submit_many(client, 2)
    before = _live_count(app)
    _inject_unknown_event(app)
    _service(app).verify()
    assert _live_count(app) == before
    with app.state.session_factory() as session:
        # Shadow was cleaned; no half-built rows linger.
        assert session.scalar(select(func.count()).select_from(AcceptedObservationShadowRow)) == 0


def test_rebuild_promotion_is_atomic(app: FastAPI, client: TestClient) -> None:
    _submit_many(client, 3)
    with app.state.session_factory() as session:
        session.execute(text("DELETE FROM accepted_observations"))
        session.commit()
    assert _live_count(app) == 0

    result = _service(app).rebuild(from_scratch=True)
    assert result.rows_written == 3
    # Promotion moved all shadow rows to live and cleared the shadow.
    assert _live_count(app) == 3
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AcceptedObservationShadowRow)) == 0


def test_failed_promotion_rolls_back(app: FastAPI, client: TestClient) -> None:
    _submit_many(client, 2)
    before = _live_count(app)
    _inject_unknown_event(app)

    # Rebuild fails on the unknown event BEFORE any promotion: live is never
    # emptied, and no shadow rows are promoted.
    with pytest.raises(UnknownProjectionEventError):
        _service(app).rebuild(from_scratch=True)

    assert _live_count(app) == before
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AcceptedObservationShadowRow)) == 0


def test_reads_continue_during_verify(app: FastAPI, client: TestClient) -> None:
    _submit_many(client, 2)
    listing = client.get("/api/v1/observations")
    assert listing.status_code == 200
    observations = listing.json()["data"]["items"]
    assert len(observations) == 2

    _service(app).verify()

    # Live reads keep working and return the same rows after verify.
    after = client.get("/api/v1/observations")
    assert after.status_code == 200
    assert len(after.json()["data"]["items"]) == 2
