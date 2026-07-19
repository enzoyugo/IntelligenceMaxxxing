"""Incremental integrity verification (Stage 1.1 §5).

INCREMENTAL_VALID_CHAIN_PASSES
INCREMENTAL_USES_PREVIOUS_HASH_ANCHOR
INCREMENTAL_DETECTS_NEW_TAMPERING
INCREMENTAL_WITHOUT_CHECKPOINT_FALLS_BACK_SAFELY
FULL_AND_INCREMENTAL_AGREE
CHECKPOINT_NOT_ADVANCED_ON_FAILURE
"""

import uuid
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from intelligence_maxxxing import API_VERSION
from intelligence_maxxxing.application.use_cases.integrity import (
    IntegrityVerificationService,
    NoOpIntegrityViolationHook,
)
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

TENANT, OWNER, APP = "tnt_t", "usr_o", "app_a"


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


def _event(obs_id: str) -> EngineEvent:
    now = utc_now()
    return EngineEvent(
        event_id=f"evt_{uuid.uuid4().hex}",
        event_type="ObservationAccepted",
        aggregate_type="Observation",
        aggregate_id=obs_id,
        aggregate_version=1,
        tenant_id=TENANT,
        owner_id=OWNER,
        application_id=APP,
        actor=Actor(actor_type=ActorType.APPLICATION, actor_id=APP),
        schema_version="1.0",
        payload=_payload(obs_id),
        occurred_at=now,
        recorded_at=now,
        audit_id="aud_" + "a" * 32,
        request_id="req_" + "a" * 32,
    )


def _service(factory: sessionmaker) -> IntegrityVerificationService:
    snapshot = HealthSnapshot(
        snapshot_id="hsnap_test",
        checked_at=utc_now(),
        components=(
            HealthComponentStatus(component="database", state=HealthState.HEALTHY, checked=True),
        ),
    )
    return IntegrityVerificationService(
        uow=SqlAlchemyUnitOfWork(factory),
        engine_version="0.1.0",
        api_version=API_VERSION,
        health_provider=StaticHealthSnapshotProvider(snapshot),
        violation_hook=NoOpIntegrityViolationHook(),
    )


def _append(factory: sessionmaker, count: int) -> list[str]:
    ids = []
    with factory() as session:
        store = SqlAlchemyEventStore(session)
        for _ in range(count):
            obs_id = "obs_" + uuid.uuid4().hex
            store.append_one(_event(obs_id))
            ids.append(obs_id)
        session.commit()
    return ids


def _make(tmp_path: Path) -> sessionmaker:
    engine = create_engine(f"sqlite:///{tmp_path / 'inc.sqlite3'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_incremental_valid_chain_passes(tmp_path: Path) -> None:
    factory = _make(tmp_path)
    _append(factory, 3)
    svc = _service(factory)
    assert svc.verify(mode="FULL").ok is True
    _append(factory, 2)
    report = svc.verify(mode="INCREMENTAL")
    assert report.ok is True
    assert report.mode == "INCREMENTAL"


def test_incremental_uses_previous_hash_anchor(tmp_path: Path) -> None:
    """The first event after the checkpoint chains onto the checkpoint hash;
    a legitimate anchor must not be mistaken for corruption."""
    factory = _make(tmp_path)
    _append(factory, 2)
    svc = _service(factory)
    assert svc.verify(mode="FULL").ok is True

    with factory() as session:
        from intelligence_maxxxing.infrastructure.repositories.integrity import (
            SqlAlchemyIntegrityStore,
        )

        checkpoint = SqlAlchemyIntegrityStore(session).get_integrity_checkpoint(TENANT, OWNER, APP)
    assert checkpoint is not None
    assert checkpoint.last_verified_hash is not None

    _append(factory, 1)
    # Without the anchor, the first post-checkpoint event (whose
    # previous_event_hash equals the anchor) would be flagged. It must pass.
    assert svc.verify(mode="INCREMENTAL").ok is True


def test_incremental_detects_new_tampering(tmp_path: Path) -> None:
    factory = _make(tmp_path)
    _append(factory, 2)
    svc = _service(factory)
    assert svc.verify(mode="FULL").ok is True

    new_ids = _append(factory, 2)
    # Tamper the stored hash of a NEW event (after the checkpoint).
    with factory() as session:
        session.execute(
            text("UPDATE engine_events SET event_hash = :h WHERE aggregate_id = :aid"),
            {"h": "f" * 64, "aid": new_ids[-1]},
        )
        session.commit()
    report = svc.verify(mode="INCREMENTAL")
    assert report.ok is False
    assert len(report.violations) == 1


def test_incremental_without_checkpoint_falls_back_safely(tmp_path: Path) -> None:
    factory = _make(tmp_path)
    _append(factory, 3)
    svc = _service(factory)
    # No checkpoint yet: INCREMENTAL must verify the whole stream from zero.
    report = svc.verify(mode="INCREMENTAL")
    assert report.ok is True
    assert report.events_checked >= 3


def test_full_and_incremental_agree(tmp_path: Path) -> None:
    factory = _make(tmp_path)
    _append(factory, 4)
    svc = _service(factory)
    full = svc.verify(mode="FULL")
    incremental = svc.verify(mode="INCREMENTAL")
    assert full.ok == incremental.ok is True


def test_checkpoint_not_advanced_on_failure(tmp_path: Path) -> None:
    factory = _make(tmp_path)
    ids = _append(factory, 3)
    # Tamper before any successful verification: no checkpoint should be written.
    with factory() as session:
        session.execute(
            text("UPDATE engine_events SET event_hash = :h WHERE aggregate_id = :aid"),
            {"h": "0" * 64, "aid": ids[1]},
        )
        session.commit()
    svc = _service(factory)
    report = svc.verify(mode="FULL")
    assert report.ok is False

    with factory() as session:
        from intelligence_maxxxing.infrastructure.repositories.integrity import (
            SqlAlchemyIntegrityStore,
        )

        checkpoint = SqlAlchemyIntegrityStore(session).get_integrity_checkpoint(TENANT, OWNER, APP)
    # The failed stream's checkpoint was never advanced.
    assert checkpoint is None
