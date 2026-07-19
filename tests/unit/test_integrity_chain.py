"""Integrity chain unit tests.

EVENT_HASH_DETERMINISTIC / EVENT_CHAIN_VERIFIES / EVENT_TAMPERING_DETECTED /
INTEGRITY_FAILURE_EMITS_ALERT
"""

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from intelligence_maxxxing import API_VERSION
from intelligence_maxxxing.application.use_cases.integrity import (
    IntegrityVerificationService,
    NoOpIntegrityViolationHook,
)
from intelligence_maxxxing.domain.audit.integrity import compute_event_hash, verify_chain
from intelligence_maxxxing.domain.audit.models import Actor, EngineEvent
from intelligence_maxxxing.domain.common.base import utc_now
from intelligence_maxxxing.domain.common.epistemic import ActorType, KnowledgeClass
from intelligence_maxxxing.domain.common.health import (
    HealthComponentStatus,
    HealthSnapshot,
    HealthState,
)
from intelligence_maxxxing.infrastructure.database import Base
from intelligence_maxxxing.infrastructure.event_store import SqlAlchemyEventStore
from intelligence_maxxxing.infrastructure.health import StaticHealthSnapshotProvider
from intelligence_maxxxing.infrastructure.repositories import SqlAlchemyUnitOfWork


def _payload(statement: str) -> dict[str, object]:
    now = utc_now().isoformat()
    return {
        "id": "obs_" + "d" * 32,
        "schema_version": "1.0",
        "domain_pack": "core",
        "subject": "sleep",
        "context": {"schema_version": "1.0", "scope": "personal", "tenant_id": "tnt_t"},
        "created_at": now,
        "source_ids": [],
        "metadata": {},
        "knowledge_class": KnowledgeClass.OBSERVED_FACT.value,
        "statement": statement,
        "audit_id": "aud_" + "d" * 32,
        "observed_by": "t",
    }


def _event(event_id: str, statement: str = "s") -> EngineEvent:
    now = utc_now()
    return EngineEvent(
        event_id=event_id,
        event_type="ObservationAccepted",
        aggregate_type="Observation",
        aggregate_id="obs_" + "d" * 32,
        aggregate_version=1,
        tenant_id="tnt_t",
        owner_id="usr_t",
        application_id="app_t",
        actor=Actor(actor_type=ActorType.APPLICATION, actor_id="app_t"),
        schema_version="1.0",
        payload=_payload(statement),
        occurred_at=now,
        recorded_at=now,
        audit_id="aud_" + "d" * 32,
        request_id="req_" + "d" * 32,
    )


def test_event_hash_deterministic() -> None:
    event = _event("evt_" + "a" * 32)
    h1 = compute_event_hash(event, None)
    h2 = compute_event_hash(event, None)
    assert h1 == h2
    assert len(h1) == 64


def test_event_chain_verifies(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'chain.sqlite3'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    store = SqlAlchemyEventStore(session)

    e1 = _event("evt_" + "1" * 32, "one")
    now = utc_now()
    e2 = EngineEvent(
        event_id="evt_" + "2" * 32,
        event_type="ObservationAccepted",
        aggregate_type="Observation",
        aggregate_id="obs_" + "e" * 32,
        aggregate_version=1,
        tenant_id="tnt_t",
        owner_id="usr_t",
        application_id="app_t",
        actor=Actor(actor_type=ActorType.APPLICATION, actor_id="app_t"),
        schema_version="1.0",
        payload=_payload("two") | {"id": "obs_" + "e" * 32},
        occurred_at=now,
        recorded_at=now,
        audit_id="aud_" + "d" * 32,
        request_id="req_" + "e" * 32,
    )
    p1 = store.append_one(e1)
    p2 = store.append_one(e2)
    session.commit()

    ok, broken = verify_chain([p1, p2])
    assert ok is True
    assert broken is None
    assert p1.event_hash is not None
    assert p2.previous_event_hash == p1.event_hash


def test_event_tampering_detected(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'tamper.sqlite3'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    store = SqlAlchemyEventStore(session)
    persisted = store.append_one(_event("evt_" + "3" * 32))
    session.commit()

    # Corrupt the hash column to simulate silent alteration of stored material.
    session.execute(
        text("UPDATE engine_events SET event_hash = :h WHERE event_id = :eid"),
        {"h": "f" * 64, "eid": persisted.event_id},
    )
    session.commit()

    reloaded = store.get_by_event_id(persisted.event_id)
    assert reloaded is not None
    expected = compute_event_hash(reloaded, reloaded.previous_event_hash)
    assert reloaded.event_hash != expected
    ok, broken = verify_chain([reloaded])
    assert ok is False
    assert broken == persisted.event_id


def test_integrity_failure_emits_alert(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'alert.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    store_session = factory()
    store = SqlAlchemyEventStore(store_session)
    persisted = store.append_one(_event("evt_" + "4" * 32))
    store_session.commit()

    # Corrupt the stored hash directly.
    store_session.execute(
        text("UPDATE engine_events SET event_hash = :h WHERE event_id = :eid"),
        {"h": "0" * 64, "eid": persisted.event_id},
    )
    store_session.commit()
    store_session.close()

    hook = NoOpIntegrityViolationHook()
    snapshot = HealthSnapshot(
        snapshot_id="hsnap_test",
        checked_at=utc_now(),
        components=(
            HealthComponentStatus(component="database", state=HealthState.HEALTHY, checked=True),
        ),
    )
    service = IntegrityVerificationService(
        uow=SqlAlchemyUnitOfWork(factory),
        engine_version="0.1.0",
        api_version=API_VERSION,
        health_provider=StaticHealthSnapshotProvider(snapshot),
        violation_hook=hook,
    )
    report = service.verify(mode="FULL")
    assert report.ok is False
    assert len(report.violations) == 1
    assert hook.calls
    assert hook.calls[0][2] == persisted.event_id
