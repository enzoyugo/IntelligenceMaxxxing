"""Real integrity quarantine kill-switch (Stage 1.1 §6).

INTEGRITY_VIOLATION_QUARANTINES_STREAM
QUARANTINED_STREAM_BLOCKS_WRITE
OTHER_STREAMS_REMAIN_AVAILABLE
UNQUARANTINE_REQUIRES_ADMIN
UNQUARANTINE_REQUIRES_SUCCESSFUL_FULL_VERIFY
QUARANTINE_ACTION_IS_AUDITED
"""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from intelligence_maxxxing import API_VERSION
from intelligence_maxxxing.application.errors import StreamReleaseBlockedError
from intelligence_maxxxing.application.use_cases.integrity import (
    IntegrityVerificationService,
    LoggingIntegrityViolationHook,
)
from intelligence_maxxxing.infrastructure.database.tables import EngineEventRow
from intelligence_maxxxing.infrastructure.health import (
    MeasuredHealthSnapshotProvider,
    SqlAlchemyDatabaseHealth,
)
from intelligence_maxxxing.infrastructure.repositories import SqlAlchemyUnitOfWork
from intelligence_maxxxing.infrastructure.repositories.integrity import (
    SqlAlchemyIntegrityStore,
)
from intelligence_maxxxing.permissions import PermissionScope
from tests.conftest import valid_observation_payload
from tests.fixtures.identity import (
    BootstrappedIdentity,
    bootstrap_test_identity,
    register_application_for,
)


def _integrity(app: FastAPI) -> IntegrityVerificationService:
    return IntegrityVerificationService(
        uow=SqlAlchemyUnitOfWork(app.state.session_factory),
        engine_version=app.state.settings.engine_version,
        api_version=API_VERSION,
        health_provider=MeasuredHealthSnapshotProvider(
            SqlAlchemyDatabaseHealth(app.state.db_engine), check_manifest=False
        ),
        violation_hook=LoggingIntegrityViolationHook(),
    )


def _submit(client: TestClient, identity: BootstrappedIdentity) -> str:
    response = client.post(
        "/api/v1/observations",
        json=valid_observation_payload(),
        headers={**identity.auth_header, "Idempotency-Key": f"q-{uuid.uuid4().hex}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["event_id"]


def _tamper(app: FastAPI, event_id: str) -> str:
    """Corrupt the stored hash; return the original for later repair."""
    with app.state.session_factory() as session:
        original = session.scalar(
            select(EngineEventRow.event_hash).where(EngineEventRow.event_id == event_id)
        )
        session.execute(
            text("UPDATE engine_events SET event_hash = :h WHERE event_id = :eid"),
            {"h": "f" * 64, "eid": event_id},
        )
        session.commit()
    assert original is not None
    return original


def test_integrity_violation_quarantines_stream(app: FastAPI) -> None:
    identity = bootstrap_test_identity(app, display_name="q-app")
    with TestClient(app, raise_server_exceptions=False) as client:
        event_id = _submit(client, identity)
    _tamper(app, event_id)

    report = _integrity(app).verify(mode="FULL")
    assert report.ok is False

    with app.state.session_factory() as session:
        head = SqlAlchemyIntegrityStore(session).get_stream_head(
            identity.tenant_id, identity.owner_id, identity.application_id
        )
    assert head is not None
    assert head.status == "QUARANTINED"
    assert head.broken_event_id == event_id


def test_quarantined_stream_blocks_write(app: FastAPI) -> None:
    identity = bootstrap_test_identity(app, display_name="q-block")
    with TestClient(app, raise_server_exceptions=False) as client:
        event_id = _submit(client, identity)
    _tamper(app, event_id)
    _integrity(app).verify(mode="FULL")

    with TestClient(app, raise_server_exceptions=False) as client:
        blocked = client.post(
            "/api/v1/observations",
            json=valid_observation_payload(),
            headers={**identity.auth_header, "Idempotency-Key": f"q-{uuid.uuid4().hex}"},
        )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "STREAM_QUARANTINED"


def test_other_streams_remain_available(app: FastAPI) -> None:
    app_a = bootstrap_test_identity(app, display_name="q-a")
    app_b = register_application_for(app, owner_id=app_a.owner_id, display_name="q-b")
    with TestClient(app, raise_server_exceptions=False) as client:
        event_a = _submit(client, app_a)
    _tamper(app, event_a)
    _integrity(app).verify(mode="FULL")

    with TestClient(app, raise_server_exceptions=False) as client:
        # App A's stream is quarantined...
        blocked = client.post(
            "/api/v1/observations",
            json=valid_observation_payload(),
            headers={**app_a.auth_header, "Idempotency-Key": f"q-{uuid.uuid4().hex}"},
        )
        assert blocked.status_code == 409
        # ...but App B's stream keeps working.
        ok = client.post(
            "/api/v1/observations",
            json=valid_observation_payload(),
            headers={**app_b.auth_header, "Idempotency-Key": f"q-{uuid.uuid4().hex}"},
        )
    assert ok.status_code == 201


def test_unquarantine_requires_admin(app: FastAPI) -> None:
    identity = bootstrap_test_identity(app, display_name="q-admin")
    with TestClient(app, raise_server_exceptions=False) as client:
        event_id = _submit(client, identity)
    original = _tamper(app, event_id)
    _integrity(app).verify(mode="FULL")

    # Repair the data so a full verify would succeed, to isolate the scope check.
    with app.state.session_factory() as session:
        session.execute(
            text("UPDATE engine_events SET event_hash = :h WHERE event_id = :eid"),
            {"h": original, "eid": event_id},
        )
        session.commit()

    with pytest.raises(StreamReleaseBlockedError):
        _integrity(app).unquarantine_stream(
            identity.tenant_id,
            identity.owner_id,
            identity.application_id,
            reason="manual",
            admin_actor_id="tester",
            actor_scopes=frozenset({PermissionScope.READ_AUDIT.value}),
        )


def test_unquarantine_requires_successful_full_verify(app: FastAPI) -> None:
    identity = bootstrap_test_identity(app, display_name="q-verify")
    with TestClient(app, raise_server_exceptions=False) as client:
        event_id = _submit(client, identity)
    original = _tamper(app, event_id)
    _integrity(app).verify(mode="FULL")

    admin_scopes = frozenset({PermissionScope.ADMINISTER_ENGINE.value})

    # Still tampered: release is blocked even with ADMINISTER_ENGINE.
    with pytest.raises(StreamReleaseBlockedError):
        _integrity(app).unquarantine_stream(
            identity.tenant_id,
            identity.owner_id,
            identity.application_id,
            reason="premature",
            admin_actor_id="admin",
            actor_scopes=admin_scopes,
        )

    # Repair, then release succeeds and the stream accepts writes again.
    with app.state.session_factory() as session:
        session.execute(
            text("UPDATE engine_events SET event_hash = :h WHERE event_id = :eid"),
            {"h": original, "eid": event_id},
        )
        session.commit()

    result = _integrity(app).unquarantine_stream(
        identity.tenant_id,
        identity.owner_id,
        identity.application_id,
        reason="repaired and verified",
        admin_actor_id="admin",
        actor_scopes=admin_scopes,
    )
    assert result.ok is True

    with TestClient(app, raise_server_exceptions=False) as client:
        ok = client.post(
            "/api/v1/observations",
            json=valid_observation_payload(),
            headers={**identity.auth_header, "Idempotency-Key": f"q-{uuid.uuid4().hex}"},
        )
    assert ok.status_code == 201


def test_quarantine_action_is_audited(app: FastAPI) -> None:
    identity = bootstrap_test_identity(app, display_name="q-audit")
    with TestClient(app, raise_server_exceptions=False) as client:
        event_id = _submit(client, identity)
    _tamper(app, event_id)
    _integrity(app).verify(mode="FULL")

    with app.state.session_factory() as session:
        quarantine_events = session.scalar(
            select(func.count())
            .select_from(EngineEventRow)
            .where(EngineEventRow.event_type == "IntegrityStreamQuarantined")
        )
        violation_events = session.scalar(
            select(func.count())
            .select_from(EngineEventRow)
            .where(EngineEventRow.event_type == "IntegrityViolationDetected")
        )
    assert quarantine_events == 1
    assert violation_events == 1
