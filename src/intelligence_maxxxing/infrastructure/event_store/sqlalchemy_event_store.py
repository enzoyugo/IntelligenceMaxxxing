"""SQLAlchemy implementation of the append-only event store (Stage 1 / v2).

Constitutional constraint: this class exposes append and read operations only.
No update, no delete, no upsert. Constitutional tests inspect this class and
fail if mutation methods appear.

On every append:
1. validate the payload against the event catalog;
2. compute the integrity hash chained to the previous event of the same
   (owner, application) stream;
3. insert the row (global_position is assigned by the database).
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from intelligence_maxxxing.application.errors import (
    ConcurrencyConflictError,
    IdempotencyRaceDetected,
)
from intelligence_maxxxing.application.ports import EventStorePort
from intelligence_maxxxing.contracts.events.catalog import validate_event_payload
from intelligence_maxxxing.domain.audit.integrity import compute_event_hash
from intelligence_maxxxing.domain.audit.models import Actor, EngineEvent
from intelligence_maxxxing.domain.common.epistemic import ActorType
from intelligence_maxxxing.infrastructure.database.tables import EngineEventRow


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
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        actor=Actor(actor_type=ActorType(row.actor_type), actor_id=row.actor_id),
        schema_version=row.schema_version,
        payload=row.payload,
        occurred_at=_as_utc(row.occurred_at),
        recorded_at=_as_utc(row.recorded_at),
        audit_id=row.audit_id,
        request_id=row.request_id,
        idempotency_key=row.idempotency_key,
        previous_event_hash=row.previous_event_hash,
        event_hash=row.event_hash,
        global_position=row.global_position,
    )


class SqlAlchemyEventStore(EventStorePort):
    def __init__(self, session: Session) -> None:
        self._session = session

    def append_one(self, event: EngineEvent) -> EngineEvent:
        validate_event_payload(event.event_type, event.schema_version, event.payload)
        self._assert_optimistic_concurrency(event)

        previous_hash = self._latest_stream_hash(event.owner_id, event.application_id)
        event_hash = compute_event_hash(event, previous_hash)

        # When an event carries an idempotency key, record the action scope
        # that produced it. Today that is always observations.submit; other
        # write paths will pass their own action through a future field.
        scope = "observations.submit" if event.idempotency_key else None
        row = EngineEventRow(
            event_id=event.event_id,
            event_type=event.event_type,
            schema_version=event.schema_version,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            aggregate_version=event.aggregate_version,
            domain_pack=event.domain_pack,
            tenant_id=event.tenant_id,
            owner_id=event.owner_id,
            application_id=event.application_id,
            actor_type=event.actor.actor_type.value,
            actor_id=event.actor.actor_id,
            payload=event.payload,
            occurred_at=event.occurred_at,
            recorded_at=event.recorded_at,
            audit_id=event.audit_id,
            request_id=event.request_id,
            idempotency_scope=scope,
            idempotency_key=event.idempotency_key,
            previous_event_hash=previous_hash,
            event_hash=event_hash,
        )
        self._session.add(row)
        try:
            self._session.flush()  # assign global_position / detect conflicts early
        except IntegrityError as exc:
            message = str(exc.orig) if exc.orig is not None else str(exc)
            if "idempotency" in message.lower():
                raise IdempotencyRaceDetected(
                    "concurrent request with the same idempotency scope committed first"
                ) from exc
            raise
        return _row_to_event(row)

    def append_batch(self, events: Sequence[EngineEvent]) -> Sequence[EngineEvent]:
        return [self.append_one(event) for event in events]

    def get_by_event_id(self, event_id: str) -> EngineEvent | None:
        stmt = select(EngineEventRow).where(EngineEventRow.event_id == event_id)
        row = self._session.scalars(stmt).first()
        return _row_to_event(row) if row is not None else None

    def list_by_aggregate(self, owner_id: str, aggregate_id: str) -> Sequence[EngineEvent]:
        stmt = (
            select(EngineEventRow)
            .where(
                EngineEventRow.owner_id == owner_id,
                EngineEventRow.aggregate_id == aggregate_id,
            )
            .order_by(EngineEventRow.aggregate_version)
        )
        return [_row_to_event(row) for row in self._session.scalars(stmt)]

    def list_by_audit(self, owner_id: str, audit_id: str) -> Sequence[EngineEvent]:
        stmt = (
            select(EngineEventRow)
            .where(
                EngineEventRow.owner_id == owner_id,
                EngineEventRow.audit_id == audit_id,
            )
            .order_by(EngineEventRow.global_position)
        )
        return [_row_to_event(row) for row in self._session.scalars(stmt)]

    def list_by_owner(
        self, owner_id: str, application_id: str | None = None
    ) -> Sequence[EngineEvent]:
        stmt = select(EngineEventRow).where(EngineEventRow.owner_id == owner_id)
        if application_id is not None:
            stmt = stmt.where(EngineEventRow.application_id == application_id)
        stmt = stmt.order_by(EngineEventRow.global_position)
        return [_row_to_event(row) for row in self._session.scalars(stmt)]

    def stream_from_position(self, position: int, limit: int) -> Sequence[EngineEvent]:
        stmt = (
            select(EngineEventRow)
            .where(EngineEventRow.global_position > position)
            .order_by(EngineEventRow.global_position)
            .limit(limit)
        )
        return [_row_to_event(row) for row in self._session.scalars(stmt)]

    def stream_for_stream_key(
        self, owner_id: str, application_id: str, from_position: int = 0
    ) -> Sequence[EngineEvent]:
        stmt = (
            select(EngineEventRow)
            .where(
                EngineEventRow.owner_id == owner_id,
                EngineEventRow.application_id == application_id,
                EngineEventRow.global_position > from_position,
            )
            .order_by(EngineEventRow.global_position)
        )
        return [_row_to_event(row) for row in self._session.scalars(stmt)]

    def list_stream_keys(self) -> Sequence[tuple[str, str]]:
        stmt = (
            select(EngineEventRow.owner_id, EngineEventRow.application_id)
            .distinct()
            .order_by(EngineEventRow.owner_id, EngineEventRow.application_id)
        )
        return [(owner, app) for owner, app in self._session.execute(stmt)]

    def get_latest_aggregate_version(self, aggregate_type: str, aggregate_id: str) -> int | None:
        stmt = (
            select(EngineEventRow.aggregate_version)
            .where(
                EngineEventRow.aggregate_type == aggregate_type,
                EngineEventRow.aggregate_id == aggregate_id,
            )
            .order_by(EngineEventRow.aggregate_version.desc())
            .limit(1)
        )
        return self._session.scalars(stmt).first()

    def _latest_stream_hash(self, owner_id: str, application_id: str) -> str | None:
        stmt = (
            select(EngineEventRow.event_hash)
            .where(
                EngineEventRow.owner_id == owner_id,
                EngineEventRow.application_id == application_id,
                EngineEventRow.event_hash.is_not(None),
            )
            .order_by(EngineEventRow.global_position.desc())
            .limit(1)
        )
        return self._session.scalars(stmt).first()

    def _assert_optimistic_concurrency(self, event: EngineEvent) -> None:
        latest = self.get_latest_aggregate_version(event.aggregate_type, event.aggregate_id)
        expected_previous = event.aggregate_version - 1
        if latest is None:
            if event.aggregate_version != 1:
                raise ConcurrencyConflictError(
                    f"aggregate {event.aggregate_id} has no history; "
                    f"expected version 1, got {event.aggregate_version}"
                )
            return
        if latest != expected_previous:
            raise ConcurrencyConflictError(
                f"aggregate {event.aggregate_id} expected previous version "
                f"{expected_previous}, found {latest}"
            )
