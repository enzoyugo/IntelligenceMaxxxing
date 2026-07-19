"""Application-scoped aggregate identity (Stage 1.1 §7).

SAME_AGGREGATE_ID_DIFFERENT_APPLICATION_ALLOWED
SAME_AGGREGATE_ID_DIFFERENT_OWNER_ALLOWED
SAME_AGGREGATE_VERSION_SAME_SCOPE_REJECTED
AGGREGATE_LOOKUP_NEVER_CROSSES_APPLICATION
"""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from intelligence_maxxxing.application.errors import ConcurrencyConflictError
from intelligence_maxxxing.domain.audit.models import Actor, EngineEvent
from intelligence_maxxxing.domain.common.base import utc_now
from intelligence_maxxxing.domain.common.epistemic import ActorType, KnowledgeClass
from intelligence_maxxxing.infrastructure.database import Base
from intelligence_maxxxing.infrastructure.event_store import SqlAlchemyEventStore

AGG = "obs_" + "a" * 32


def _payload(statement: str) -> dict[str, object]:
    now = utc_now().isoformat()
    return {
        "id": AGG,
        "schema_version": "1.0",
        "domain_pack": "core",
        "subject": "sleep",
        "context": {"schema_version": "1.0", "scope": "personal", "tenant_id": "tnt_t"},
        "created_at": now,
        "source_ids": [],
        "metadata": {},
        "knowledge_class": KnowledgeClass.OBSERVED_FACT.value,
        "statement": statement,
        "audit_id": "aud_" + "a" * 32,
        "observed_by": "t",
    }


def _event(
    *,
    tenant: str,
    owner: str,
    application: str,
    version: int = 1,
    aggregate_id: str = AGG,
) -> EngineEvent:
    now = utc_now()
    return EngineEvent(
        event_id=f"evt_{uuid.uuid4().hex}",
        event_type="ObservationAccepted",
        aggregate_type="Observation",
        aggregate_id=aggregate_id,
        aggregate_version=version,
        tenant_id=tenant,
        owner_id=owner,
        application_id=application,
        actor=Actor(actor_type=ActorType.APPLICATION, actor_id=application),
        schema_version="1.0",
        payload=_payload("s"),
        occurred_at=now,
        recorded_at=now,
        audit_id="aud_" + "a" * 32,
        request_id="req_" + "a" * 32,
    )


@pytest.fixture()
def store(tmp_path: Path) -> SqlAlchemyEventStore:
    engine = create_engine(f"sqlite:///{tmp_path / 'agg.sqlite3'}")
    Base.metadata.create_all(engine)
    session: Session = sessionmaker(bind=engine)()
    return SqlAlchemyEventStore(session)


def test_same_aggregate_id_different_application_allowed(store: SqlAlchemyEventStore) -> None:
    store.append_one(_event(tenant="tnt_t", owner="usr_o", application="app_a"))
    # Same aggregate id + version under a DIFFERENT application: distinct stream.
    store.append_one(_event(tenant="tnt_t", owner="usr_o", application="app_b"))
    store._session.commit()
    assert store.get_latest_aggregate_version("tnt_t", "usr_o", "app_a", "Observation", AGG) == 1
    assert store.get_latest_aggregate_version("tnt_t", "usr_o", "app_b", "Observation", AGG) == 1


def test_same_aggregate_id_different_owner_allowed(store: SqlAlchemyEventStore) -> None:
    store.append_one(_event(tenant="tnt_t", owner="usr_a", application="app_x"))
    store.append_one(_event(tenant="tnt_t", owner="usr_b", application="app_x"))
    store._session.commit()
    assert store.get_latest_aggregate_version("tnt_t", "usr_a", "app_x", "Observation", AGG) == 1
    assert store.get_latest_aggregate_version("tnt_t", "usr_b", "app_x", "Observation", AGG) == 1


def test_same_aggregate_version_same_scope_rejected(store: SqlAlchemyEventStore) -> None:
    store.append_one(_event(tenant="tnt_t", owner="usr_o", application="app_a"))
    store._session.commit()
    with pytest.raises((ConcurrencyConflictError, Exception)):
        store.append_one(_event(tenant="tnt_t", owner="usr_o", application="app_a", version=1))
        store._session.flush()


def test_aggregate_lookup_never_crosses_application(store: SqlAlchemyEventStore) -> None:
    store.append_one(_event(tenant="tnt_t", owner="usr_o", application="app_a"))
    store.append_one(_event(tenant="tnt_t", owner="usr_o", application="app_b"))
    store._session.commit()

    a_events = store.list_by_aggregate("tnt_t", "usr_o", "app_a", AGG)
    b_events = store.list_by_aggregate("tnt_t", "usr_o", "app_b", AGG)
    assert len(a_events) == 1
    assert len(b_events) == 1
    assert a_events[0].application_id == "app_a"
    assert b_events[0].application_id == "app_b"
    # A lookup in a third application sees nothing.
    assert store.list_by_aggregate("tnt_t", "usr_o", "app_c", AGG) == []
