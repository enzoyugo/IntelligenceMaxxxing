"""Stage 1.1 hardening on REAL PostgreSQL (concurrency, isolation, integrity).

CONCURRENT_DISTINCT_EVENTS_SAME_STREAM_FORM_ONE_CHAIN
CONCURRENT_EVENTS_DIFFERENT_STREAMS_DO_NOT_BLOCK_GLOBALLY
STREAM_HEAD_MATCHES_LAST_EVENT
APPEND_BATCH_CHAINS_IN_INPUT_ORDER
STREAM_HEAD_UPDATE_IS_ATOMIC
FAILED_APPEND_DOES_NOT_ADVANCE_STREAM_HEAD
QUARANTINED_STREAM_REJECTS_APPEND
CROSS_APPLICATION_AUDIT_EXPLOIT_REGRESSION (App B -> App A audit == 404)
FULL_AND_INCREMENTAL_AGREE
SHADOW_PROJECTION_VERIFY_ON_POSTGRES
"""

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from intelligence_maxxxing import API_VERSION
from intelligence_maxxxing.application.errors import StreamQuarantinedError
from intelligence_maxxxing.application.use_cases.integrity import (
    IntegrityVerificationService,
    NoOpIntegrityViolationHook,
)
from intelligence_maxxxing.application.use_cases.projections import ProjectionRebuildService
from intelligence_maxxxing.domain.audit.integrity import verify_chain
from intelligence_maxxxing.domain.audit.models import Actor, EngineEvent
from intelligence_maxxxing.domain.common.base import utc_now
from intelligence_maxxxing.domain.common.epistemic import ActorType, KnowledgeClass
from intelligence_maxxxing.infrastructure.event_store import SqlAlchemyEventStore
from intelligence_maxxxing.infrastructure.health import (
    MeasuredHealthSnapshotProvider,
    SqlAlchemyDatabaseHealth,
)
from intelligence_maxxxing.infrastructure.repositories import SqlAlchemyUnitOfWork
from intelligence_maxxxing.infrastructure.repositories.integrity import (
    SqlAlchemyIntegrityStore,
)
from tests.conftest import valid_observation_payload
from tests.fixtures.identity import (
    bootstrap_test_identity,
    register_application_for,
)

pytestmark = pytest.mark.postgres

TENANT = "tnt_pg_stage11"


def _payload(obs_id: str) -> dict[str, object]:
    now = utc_now().isoformat()
    return {
        "id": obs_id,
        "schema_version": "1.0",
        "domain_pack": "core",
        "subject": "sleep",
        "context": {"schema_version": "1.0", "scope": "personal", "tenant_id": TENANT},
        "created_at": now,
        "source_ids": [],
        "metadata": {},
        "knowledge_class": KnowledgeClass.OBSERVED_FACT.value,
        "statement": "s",
        "audit_id": "aud_" + "a" * 32,
        "observed_by": "t",
    }


def _event(owner: str, application: str, *, aggregate_id: str, version: int = 1) -> EngineEvent:
    now = utc_now()
    return EngineEvent(
        event_id=f"evt_{uuid.uuid4().hex}",
        event_type="ObservationAccepted",
        aggregate_type="Observation",
        aggregate_id=aggregate_id,
        aggregate_version=version,
        tenant_id=TENANT,
        owner_id=owner,
        application_id=application,
        actor=Actor(actor_type=ActorType.APPLICATION, actor_id=application),
        schema_version="1.0",
        payload=_payload(aggregate_id),
        occurred_at=now,
        recorded_at=now,
        audit_id="aud_" + "a" * 32,
        request_id="req_" + "a" * 32,
    )


def _append_one(pg_app: FastAPI, event: EngineEvent) -> None:
    with pg_app.state.session_factory() as session:
        SqlAlchemyEventStore(session).append_one(event)
        session.commit()


def test_concurrent_distinct_events_same_stream_form_one_chain(pg_app: FastAPI) -> None:
    owner, application = f"usr_{uuid.uuid4().hex[:8]}", "app_same"
    total = 20

    def worker(_: int) -> None:
        _append_one(pg_app, _event(owner, application, aggregate_id="obs_" + uuid.uuid4().hex))

    with ThreadPoolExecutor(max_workers=total) as pool:
        for future in as_completed([pool.submit(worker, i) for i in range(total)]):
            future.result()

    with pg_app.state.session_factory() as session:
        store = SqlAlchemyEventStore(session)
        events = list(store.list_by_audit(TENANT, owner, application, "aud_" + "a" * 32))
        events_sorted = sorted(events, key=lambda e: e.global_position or 0)
        ok, broken = verify_chain(events_sorted)
        head = SqlAlchemyIntegrityStore(session).get_stream_head(TENANT, owner, application)

    assert len(events_sorted) == total  # events written = 20
    assert ok is True and broken is None  # chain valid = true
    assert head is not None
    assert head.stream_version == total  # one head, monotonic
    assert head.current_event_hash == events_sorted[-1].event_hash  # head hash = last event hash
    assert head.last_event_id == events_sorted[-1].event_id


def test_concurrent_events_different_streams_do_not_block_globally(pg_app: FastAPI) -> None:
    owner = f"usr_{uuid.uuid4().hex[:8]}"
    apps = [f"app_{i}" for i in range(20)]

    def worker(application: str) -> None:
        _append_one(pg_app, _event(owner, application, aggregate_id="obs_" + uuid.uuid4().hex))

    with ThreadPoolExecutor(max_workers=20) as pool:
        for future in as_completed([pool.submit(worker, a) for a in apps]):
            future.result()

    with pg_app.state.session_factory() as session:
        integrity = SqlAlchemyIntegrityStore(session)
        for application in apps:
            head = integrity.get_stream_head(TENANT, owner, application)
            assert head is not None
            assert head.stream_version == 1


def test_stream_head_matches_last_event(pg_app: FastAPI) -> None:
    owner, application = f"usr_{uuid.uuid4().hex[:8]}", "app_head"
    last_hash = None
    last_id = None
    for _ in range(3):
        event = _event(owner, application, aggregate_id="obs_" + uuid.uuid4().hex)
        _append_one(pg_app, event)
    with pg_app.state.session_factory() as session:
        store = SqlAlchemyEventStore(session)
        events = sorted(
            store.list_by_audit(TENANT, owner, application, "aud_" + "a" * 32),
            key=lambda e: e.global_position or 0,
        )
        head = SqlAlchemyIntegrityStore(session).get_stream_head(TENANT, owner, application)
        last_hash = events[-1].event_hash
        last_id = events[-1].event_id
    assert head is not None
    assert head.current_event_hash == last_hash
    assert head.last_event_id == last_id
    assert head.stream_version == 3


def test_append_batch_chains_in_input_order(pg_app: FastAPI) -> None:
    owner, application = f"usr_{uuid.uuid4().hex[:8]}", "app_batch"
    batch = [_event(owner, application, aggregate_id="obs_" + uuid.uuid4().hex) for _ in range(5)]
    with pg_app.state.session_factory() as session:
        store = SqlAlchemyEventStore(session)
        store.append_batch(batch)
        session.commit()

    with pg_app.state.session_factory() as session:
        store = SqlAlchemyEventStore(session)
        stored = sorted(
            store.list_by_audit(TENANT, owner, application, "aud_" + "a" * 32),
            key=lambda e: e.global_position or 0,
        )
    # Input order preserved and chained.
    assert [e.event_id for e in stored] == [e.event_id for e in batch]
    ok, broken = verify_chain(stored)
    assert ok is True and broken is None


def test_stream_head_update_is_atomic(pg_app: FastAPI) -> None:
    owner, application = f"usr_{uuid.uuid4().hex[:8]}", "app_atomic"
    total = 20

    def worker(_: int) -> None:
        _append_one(pg_app, _event(owner, application, aggregate_id="obs_" + uuid.uuid4().hex))

    with ThreadPoolExecutor(max_workers=total) as pool:
        for future in as_completed([pool.submit(worker, i) for i in range(total)]):
            future.result()

    with pg_app.state.session_factory() as session:
        head = SqlAlchemyIntegrityStore(session).get_stream_head(TENANT, owner, application)
    assert head is not None
    # No lost updates: exactly `total` advances happened.
    assert head.stream_version == total
    assert head.last_global_position > 0


def test_failed_append_does_not_advance_stream_head(pg_app: FastAPI) -> None:
    owner, application = f"usr_{uuid.uuid4().hex[:8]}", "app_fail"
    aggregate_id = "obs_" + uuid.uuid4().hex
    _append_one(pg_app, _event(owner, application, aggregate_id=aggregate_id, version=1))

    with pg_app.state.session_factory() as session:
        head_before = SqlAlchemyIntegrityStore(session).get_stream_head(TENANT, owner, application)
    assert head_before is not None and head_before.stream_version == 1

    # Duplicate (aggregate_id, version) violates the scoped unique constraint.
    with (
        pytest.raises(Exception),  # noqa: B017 - IntegrityError family
        pg_app.state.session_factory() as session,
    ):
        SqlAlchemyEventStore(session).append_one(
            _event(owner, application, aggregate_id=aggregate_id, version=1)
        )
        session.commit()

    with pg_app.state.session_factory() as session:
        head_after = SqlAlchemyIntegrityStore(session).get_stream_head(TENANT, owner, application)
    assert head_after is not None
    # The failed transaction rolled back the head update too.
    assert head_after.stream_version == 1
    assert head_after.current_event_hash == head_before.current_event_hash


def test_quarantined_stream_rejects_append(pg_app: FastAPI) -> None:
    owner, application = f"usr_{uuid.uuid4().hex[:8]}", "app_quar"
    _append_one(pg_app, _event(owner, application, aggregate_id="obs_" + uuid.uuid4().hex))

    with pg_app.state.session_factory() as session:
        SqlAlchemyIntegrityStore(session).quarantine_stream(
            TENANT,
            owner,
            application,
            reason="manual test quarantine",
            broken_event_id="evt_broken",
            audit_id="aud_" + "q" * 32,
            detected_at=utc_now(),
        )
        session.commit()

    with (
        pytest.raises(StreamQuarantinedError),
        pg_app.state.session_factory() as session,
    ):
        SqlAlchemyEventStore(session).append_one(
            _event(owner, application, aggregate_id="obs_" + uuid.uuid4().hex)
        )
        session.commit()


def test_cross_application_audit_exploit_regression(pg_app: FastAPI) -> None:
    """App B cannot read App A's audit under the SAME owner: 404, not 403."""
    app_a = bootstrap_test_identity(pg_app, display_name="pg-exploit-a")
    app_b = register_application_for(pg_app, owner_id=app_a.owner_id, display_name="pg-exploit-b")
    with TestClient(pg_app, raise_server_exceptions=False) as client:
        created = client.post(
            "/api/v1/observations",
            json=valid_observation_payload(),
            headers={**app_a.auth_header, "Idempotency-Key": f"pg-x-{uuid.uuid4().hex}"},
        )
        assert created.status_code == 201
        audit_id = created.json()["data"]["audit_id"]

        leaked = client.get(f"/api/v1/audits/{audit_id}", headers=app_b.auth_header)
        assert leaked.status_code == 404
        assert leaked.json()["error"]["code"] == "AUDIT_NOT_FOUND"

        own = client.get(f"/api/v1/audits/{audit_id}", headers=app_a.auth_header)
        assert own.status_code == 200


def _integrity(pg_app: FastAPI) -> IntegrityVerificationService:
    return IntegrityVerificationService(
        uow=SqlAlchemyUnitOfWork(pg_app.state.session_factory),
        engine_version=pg_app.state.settings.engine_version,
        api_version=API_VERSION,
        health_provider=MeasuredHealthSnapshotProvider(
            SqlAlchemyDatabaseHealth(pg_app.state.db_engine), check_manifest=False
        ),
        violation_hook=NoOpIntegrityViolationHook(),
    )


def test_full_and_incremental_agree(pg_app: FastAPI, pg_client: TestClient) -> None:
    for _ in range(5):
        assert (
            pg_client.post(
                "/api/v1/observations",
                json=valid_observation_payload(),
                headers={"Idempotency-Key": f"pg-int-{uuid.uuid4().hex}"},
            ).status_code
            == 201
        )
    svc = _integrity(pg_app)
    full = svc.verify(mode="FULL")
    incremental = svc.verify(mode="INCREMENTAL")
    assert full.ok is True
    assert incremental.ok is True


def test_shadow_projection_verify_on_postgres(pg_app: FastAPI, pg_client: TestClient) -> None:
    for _ in range(4):
        assert (
            pg_client.post(
                "/api/v1/observations",
                json=valid_observation_payload(),
                headers={"Idempotency-Key": f"pg-shadow-{uuid.uuid4().hex}"},
            ).status_code
            == 201
        )
    service = ProjectionRebuildService(
        uow=SqlAlchemyUnitOfWork(pg_app.state.session_factory),
        engine_version=pg_app.state.settings.engine_version,
        api_version=API_VERSION,
        health_provider=MeasuredHealthSnapshotProvider(
            SqlAlchemyDatabaseHealth(pg_app.state.db_engine), check_manifest=False
        ),
    )
    # The session-scoped gate DB is shared across tests; sync live to the full
    # ledger first (atomic promote), then a non-destructive verify must match.
    service.rebuild(from_scratch=True)
    report = service.verify()
    assert report.matches is True
    assert report.ok is True
    assert report.shadow_checksum == report.live_checksum
