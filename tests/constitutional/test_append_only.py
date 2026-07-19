"""Append-only protections.

EVENT_STORE_EXPOSES_NO_UPDATE / EVENT_STORE_EXPOSES_NO_DELETE /
EVENTS_ARE_APPEND_ONLY / CURRENT_STATE_DOES_NOT_OVERWRITE_HISTORY
"""

from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from intelligence_maxxxing.application.ports import AuditStorePort, EventStorePort
from intelligence_maxxxing.domain.audit.models import Actor, EngineEvent
from intelligence_maxxxing.domain.common.base import utc_now
from intelligence_maxxxing.domain.common.epistemic import ActorType, KnowledgeClass
from intelligence_maxxxing.infrastructure.audit import SqlAlchemyAuditStore
from intelligence_maxxxing.infrastructure.database import Base
from intelligence_maxxxing.infrastructure.event_store import SqlAlchemyEventStore

FORBIDDEN_METHOD_MARKERS = ("update", "delete", "remove", "upsert", "overwrite", "purge")

OWNER = "usr_testowner"
APP = "app_testapp"


def _public_methods(cls: type) -> list[str]:
    return [name for name in dir(cls) if not name.startswith("_") and callable(getattr(cls, name))]


@pytest.mark.parametrize(
    "cls", [EventStorePort, SqlAlchemyEventStore, AuditStorePort, SqlAlchemyAuditStore]
)
def test_event_and_audit_stores_expose_no_update_or_delete(cls: type) -> None:
    offenders = [
        name
        for name in _public_methods(cls)
        if any(marker in name.lower() for marker in FORBIDDEN_METHOD_MARKERS)
    ]
    assert not offenders, f"{cls.__name__} exposes mutation methods: {offenders}"


def _observation_payload(observation_id: str, statement: str) -> dict[str, object]:
    now = utc_now().isoformat()
    return {
        "id": observation_id,
        "schema_version": "1.0",
        "domain_pack": "core",
        "subject": "sleep",
        "context": {"schema_version": "1.0", "scope": "personal", "tenant_id": "tnt_test"},
        "created_at": now,
        "source_ids": [],
        "metadata": {},
        "knowledge_class": KnowledgeClass.OBSERVED_FACT.value,
        "statement": statement,
        "audit_id": "aud_" + "1" * 32,
        "observed_by": "tester",
    }


def _make_event(aggregate_id: str, version: int, statement: str) -> EngineEvent:
    import uuid

    now = utc_now()
    return EngineEvent(
        event_id=f"evt_{uuid.uuid4().hex}",
        event_type="ObservationAccepted",
        aggregate_type="Observation",
        aggregate_id=aggregate_id,
        aggregate_version=version,
        tenant_id="tnt_test",
        owner_id=OWNER,
        application_id=APP,
        actor=Actor(actor_type=ActorType.APPLICATION, actor_id=APP),
        schema_version="1.0",
        payload=_observation_payload(aggregate_id, statement),
        occurred_at=now,
        recorded_at=now,
        audit_id="aud_" + "1" * 32,
        request_id="req_" + "1" * 32,
    )


@pytest.fixture()
def event_store(tmp_path: Path) -> SqlAlchemyEventStore:
    engine = create_engine(f"sqlite:///{tmp_path / 'events.sqlite3'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    return SqlAlchemyEventStore(session)


def test_events_are_append_only_and_immutable(event_store: SqlAlchemyEventStore) -> None:
    event = _make_event("obs_" + "a" * 32, 1, "original")
    event_store.append_one(event)

    with pytest.raises(ValidationError):
        event.payload = {"statement": "tampered"}  # type: ignore[misc]

    stored = event_store.get_by_event_id(event.event_id)
    assert stored is not None
    assert stored.payload["statement"] == "original"


def test_new_state_does_not_overwrite_history(event_store: SqlAlchemyEventStore) -> None:
    """Appending a later version leaves earlier history byte-identical."""
    first = _make_event("obs_" + "b" * 32, 1, "version one")
    event_store.append_one(first)
    before = event_store.get_by_event_id(first.event_id)

    second = _make_event("obs_" + "b" * 32, 2, "version two")
    # Version 2 of the same aggregate needs a valid Observation payload too;
    # reuse a distinct statement. Catalog allows any valid Observation.
    event_store.append_one(second)

    after = event_store.get_by_event_id(first.event_id)
    assert before is not None and after is not None
    assert before.event_hash == after.event_hash
    assert before.payload == after.payload
    history = event_store.list_by_aggregate(OWNER, "obs_" + "b" * 32)
    assert [e.aggregate_version for e in history] == [1, 2]


def test_duplicate_aggregate_version_is_rejected(event_store: SqlAlchemyEventStore) -> None:
    """The store cannot silently replace an existing version of history."""
    from sqlalchemy.exc import IntegrityError

    event_store.append_one(_make_event("obs_" + "c" * 32, 1, "original"))
    conflicting = _make_event("obs_" + "c" * 32, 1, "rewrite attempt")
    with pytest.raises((IntegrityError, Exception)):
        event_store.append_one(conflicting)
        event_store._session.flush()
