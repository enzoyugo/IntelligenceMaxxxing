"""Projection rebuild tests.

PROJECTION_REBUILDS_FROM_ZERO / PROJECTION_REBUILD_IS_DETERMINISTIC /
PROJECTION_CHECKPOINT_RESUMES / PROJECTION_DOES_NOT_OVERWRITE_LEDGER /
UNKNOWN_EVENT_STOPS_OR_QUARANTINES_BY_POLICY
"""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from intelligence_maxxxing import API_VERSION
from intelligence_maxxxing.application.errors import UnknownProjectionEventError
from intelligence_maxxxing.application.use_cases.projections import (
    ACCEPTED_OBSERVATIONS_PROJECTION,
    ACCEPTED_OBSERVATIONS_VERSION,
    ProjectionRebuildService,
)
from intelligence_maxxxing.infrastructure.database.tables import (
    AcceptedObservationRow,
    EngineEventRow,
)
from intelligence_maxxxing.infrastructure.health import (
    MeasuredHealthSnapshotProvider,
    SqlAlchemyDatabaseHealth,
)
from intelligence_maxxxing.infrastructure.repositories import SqlAlchemyUnitOfWork
from tests.conftest import valid_observation_payload


def _rebuild(app: FastAPI, *, from_scratch: bool = True):
    return ProjectionRebuildService(
        uow=SqlAlchemyUnitOfWork(app.state.session_factory),
        engine_version=app.state.settings.engine_version,
        api_version=API_VERSION,
        health_provider=MeasuredHealthSnapshotProvider(
            SqlAlchemyDatabaseHealth(app.state.db_engine), check_manifest=False
        ),
    ).rebuild(from_scratch=from_scratch)


def test_projection_rebuilds_from_zero(app: FastAPI, client: TestClient) -> None:
    for _ in range(3):
        response = client.post(
            "/api/v1/observations",
            json=valid_observation_payload(),
            headers={"Idempotency-Key": f"proj-{uuid.uuid4().hex}"},
        )
        assert response.status_code == 201

    with app.state.session_factory() as session:
        before = list(
            session.scalars(
                select(AcceptedObservationRow).order_by(AcceptedObservationRow.global_position)
            )
        )
        session.execute(text("DELETE FROM accepted_observations"))
        session.commit()
        assert session.scalar(select(func.count()).select_from(AcceptedObservationRow)) == 0

    result = _rebuild(app, from_scratch=True)
    assert result.rows_written >= 3

    with app.state.session_factory() as session:
        after = list(
            session.scalars(
                select(AcceptedObservationRow).order_by(AcceptedObservationRow.global_position)
            )
        )
    assert [r.observation_id for r in before] == [r.observation_id for r in after]
    assert [r.statement for r in before] == [r.statement for r in after]


def test_projection_rebuild_is_deterministic(app: FastAPI, client: TestClient) -> None:
    client.post(
        "/api/v1/observations",
        json=valid_observation_payload(),
        headers={"Idempotency-Key": f"det-{uuid.uuid4().hex}"},
    )
    first = _rebuild(app, from_scratch=True)
    second = _rebuild(app, from_scratch=True)
    assert first.checksum == second.checksum
    assert first.rows_written == second.rows_written


def test_projection_checkpoint_resumes(app: FastAPI, client: TestClient) -> None:
    client.post(
        "/api/v1/observations",
        json=valid_observation_payload(),
        headers={"Idempotency-Key": f"ckpt-{uuid.uuid4().hex}"},
    )
    first = _rebuild(app, from_scratch=True)
    # Resume should scan zero new observation events (checkpoint at tip).
    resumed = _rebuild(app, from_scratch=False)
    assert resumed.last_global_position >= first.last_global_position
    with app.state.session_factory() as session:
        from intelligence_maxxxing.infrastructure.repositories.projections import (
            SqlAlchemyProjectionStore,
        )

        store = SqlAlchemyProjectionStore(session)
        checkpoint = store.get_checkpoint(
            ACCEPTED_OBSERVATIONS_PROJECTION, ACCEPTED_OBSERVATIONS_VERSION
        )
    assert checkpoint is not None
    assert checkpoint.status == "READY"


def test_projection_does_not_overwrite_ledger(app: FastAPI, client: TestClient) -> None:
    client.post(
        "/api/v1/observations",
        json=valid_observation_payload(),
        headers={"Idempotency-Key": f"led-{uuid.uuid4().hex}"},
    )
    with app.state.session_factory() as session:
        events_before = session.scalar(select(func.count()).select_from(EngineEventRow)) or 0
        session.execute(text("DELETE FROM accepted_observations"))
        session.commit()
    _rebuild(app, from_scratch=True)
    with app.state.session_factory() as session:
        events_after = session.scalar(select(func.count()).select_from(EngineEventRow)) or 0
    # Rebuild appends a ProjectionRebuilt governance event; ledger history of
    # observations is never deleted or rewritten.
    assert events_after >= events_before


def test_unknown_event_stops_or_quarantines_by_policy(app: FastAPI) -> None:
    """Inject an unregistered-to-projector event type into the ledger via SQL
    (bypassing catalog) and prove the projector fails closed."""
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
                    'evt_unknown_projection_test',
                    'TotallyUnknownForProjector',
                    '1.0', 'X', 'x1', 1, 'core',
                    'tnt_x', 'usr_x', 'app_x',
                    'SYSTEM', 'system', '{}',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP,
                    'aud_unknown_projection_test', 'req_unknown_projection_test'
                )
                """
            )
        )
        session.commit()

    with pytest.raises(UnknownProjectionEventError):
        _rebuild(app, from_scratch=True)

    with app.state.session_factory() as session:
        from intelligence_maxxxing.infrastructure.repositories.projections import (
            SqlAlchemyProjectionStore,
        )

        store = SqlAlchemyProjectionStore(session)
        checkpoint = store.get_checkpoint(
            ACCEPTED_OBSERVATIONS_PROJECTION, ACCEPTED_OBSERVATIONS_VERSION
        )
    assert checkpoint is not None
    assert checkpoint.status == "QUARANTINED"
