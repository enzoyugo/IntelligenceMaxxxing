"""SQLAlchemy implementation of the append-only event store.

Constitutional constraint: this class exposes append and read operations only.
No update, no delete, no upsert. Constitutional tests inspect this class and
fail if mutation methods appear.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from intelligence_maxxxing.application.ports import EventStorePort
from intelligence_maxxxing.domain.audit.models import Actor, EngineEvent
from intelligence_maxxxing.domain.common.epistemic import ActorType
from intelligence_maxxxing.infrastructure.database.tables import EngineEventRow

_IDEMPOTENCY_SCOPE = "observations.submit"


def _as_utc(value: datetime) -> datetime:
    """Timestamps are stored in UTC; SQLite drops tzinfo, so restore it on read."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _row_to_event(row: EngineEventRow) -> EngineEvent:
    return EngineEvent(
        event_id=row.event_id,
        event_type=row.event_type,
        aggregate_type=row.aggregate_type,
        aggregate_id=row.aggregate_id,
        aggregate_version=row.aggregate_version,
        domain_pack=row.domain_pack,
        actor=Actor(actor_type=ActorType(row.actor_type), actor_id=row.actor_id),
        schema_version=row.schema_version,
        payload=row.payload,
        occurred_at=_as_utc(row.occurred_at),
        recorded_at=_as_utc(row.recorded_at),
        audit_id=row.audit_id,
        request_id=row.request_id,
        idempotency_key=row.idempotency_key,
    )


class SqlAlchemyEventStore(EventStorePort):
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, event: EngineEvent) -> None:
        # The event is a validated frozen domain object; persistence is a pure
        # translation with no business decisions.
        row = EngineEventRow(
            event_id=event.event_id,
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            aggregate_version=event.aggregate_version,
            domain_pack=event.domain_pack,
            actor_type=event.actor.actor_type.value,
            actor_id=event.actor.actor_id,
            schema_version=event.schema_version,
            payload=event.payload,
            occurred_at=event.occurred_at,
            recorded_at=event.recorded_at,
            audit_id=event.audit_id,
            request_id=event.request_id,
            idempotency_scope=_IDEMPOTENCY_SCOPE if event.idempotency_key else None,
            idempotency_key=event.idempotency_key,
        )
        self._session.add(row)

    def get_by_event_id(self, event_id: str) -> EngineEvent | None:
        row = self._session.get(EngineEventRow, event_id)
        return _row_to_event(row) if row is not None else None

    def list_by_aggregate_id(self, aggregate_id: str) -> Sequence[EngineEvent]:
        stmt = (
            select(EngineEventRow)
            .where(EngineEventRow.aggregate_id == aggregate_id)
            .order_by(EngineEventRow.aggregate_version)
        )
        return [_row_to_event(row) for row in self._session.scalars(stmt)]

    def list_by_audit_id(self, audit_id: str) -> Sequence[EngineEvent]:
        stmt = (
            select(EngineEventRow)
            .where(EngineEventRow.audit_id == audit_id)
            .order_by(EngineEventRow.recorded_at)
        )
        return [_row_to_event(row) for row in self._session.scalars(stmt)]
