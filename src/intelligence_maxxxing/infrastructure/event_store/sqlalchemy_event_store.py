"""SQLAlchemy implementation of the append-only event store (Stage 1 / v2).

Constitutional constraint: this class exposes append and read operations only.
No update, no delete, no upsert. Constitutional tests inspect this class and
fail if mutation methods appear. (Advancing the per-stream integrity HEAD is an
internal, private part of append - not a public mutation of recorded events.)

On every append, inside ONE transaction:
1. validate the payload against the event catalog;
2. take the transactional HEAD of the (tenant, owner, application) stream with
   SELECT ... FOR UPDATE, so concurrent writers of the same stream serialize
   and chain onto each other instead of forking on a stale previous hash;
3. reject the write if the stream is QUARANTINED (kill-switch);
4. chain the integrity hash onto the head's current hash;
5. insert the row (global_position is assigned by the database);
6. advance the head atomically.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from intelligence_maxxxing.application.errors import (
    ConcurrencyConflictError,
    IdempotencyRaceDetected,
    StreamQuarantinedError,
)
from intelligence_maxxxing.application.ports import EventStorePort, StreamStatus
from intelligence_maxxxing.contracts.events.catalog import validate_event_payload
from intelligence_maxxxing.domain.audit.integrity import compute_event_hash
from intelligence_maxxxing.domain.audit.models import Actor, EngineEvent
from intelligence_maxxxing.domain.common.epistemic import ActorType
from intelligence_maxxxing.infrastructure.database.tables import (
    EngineEventRow,
    EventStreamHeadRow,
)


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


def _stream_sort_key(event: EngineEvent) -> tuple[str, str, str]:
    return (event.tenant_id, event.owner_id, event.application_id)


class SqlAlchemyEventStore(EventStorePort):
    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def _is_postgres(self) -> bool:
        return self._session.get_bind().dialect.name == "postgresql"

    def append_one(self, event: EngineEvent) -> EngineEvent:
        head = self._lock_head(event.tenant_id, event.owner_id, event.application_id)
        self._reject_if_quarantined(head)
        return self._append_with_head(event, head)

    def append_batch(self, events: Sequence[EngineEvent]) -> Sequence[EngineEvent]:
        """Append several events atomically.

        Events are grouped by (tenant, owner, application) stream. Streams are
        locked in a deterministic order (sorted by key) to avoid deadlocks
        between concurrent batches, and each stream's events are chained in
        input order. Cross-stream input order is not significant to any chain.
        """
        ordered = list(events)
        # Group preserving per-stream input order.
        groups: dict[tuple[str, str, str], list[EngineEvent]] = {}
        for event in ordered:
            groups.setdefault(_stream_sort_key(event), []).append(event)

        result_by_event_id: dict[str, EngineEvent] = {}
        for key in sorted(groups):
            tenant_id, owner_id, application_id = key
            head = self._lock_head(tenant_id, owner_id, application_id)
            self._reject_if_quarantined(head)
            for event in groups[key]:
                persisted = self._append_with_head(event, head)
                result_by_event_id[persisted.event_id] = persisted
        # Return in original input order.
        return [result_by_event_id[e.event_id] for e in ordered]

    def get_by_event_id(self, event_id: str) -> EngineEvent | None:
        stmt = select(EngineEventRow).where(EngineEventRow.event_id == event_id)
        row = self._session.scalars(stmt).first()
        return _row_to_event(row) if row is not None else None

    def list_by_aggregate(
        self,
        tenant_id: str,
        owner_id: str,
        application_id: str,
        aggregate_id: str,
    ) -> Sequence[EngineEvent]:
        stmt = (
            select(EngineEventRow)
            .where(
                EngineEventRow.tenant_id == tenant_id,
                EngineEventRow.owner_id == owner_id,
                EngineEventRow.application_id == application_id,
                EngineEventRow.aggregate_id == aggregate_id,
            )
            .order_by(EngineEventRow.aggregate_version)
        )
        return [_row_to_event(row) for row in self._session.scalars(stmt)]

    def list_by_audit(
        self,
        tenant_id: str,
        owner_id: str,
        application_id: str,
        audit_id: str,
    ) -> Sequence[EngineEvent]:
        stmt = (
            select(EngineEventRow)
            .where(
                EngineEventRow.tenant_id == tenant_id,
                EngineEventRow.owner_id == owner_id,
                EngineEventRow.application_id == application_id,
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
        self,
        tenant_id: str,
        owner_id: str,
        application_id: str,
        from_position: int = 0,
    ) -> Sequence[EngineEvent]:
        stmt = (
            select(EngineEventRow)
            .where(
                EngineEventRow.tenant_id == tenant_id,
                EngineEventRow.owner_id == owner_id,
                EngineEventRow.application_id == application_id,
                EngineEventRow.global_position > from_position,
            )
            .order_by(EngineEventRow.global_position)
        )
        return [_row_to_event(row) for row in self._session.scalars(stmt)]

    def list_stream_keys(self) -> Sequence[tuple[str, str, str]]:
        stmt = (
            select(
                EngineEventRow.tenant_id,
                EngineEventRow.owner_id,
                EngineEventRow.application_id,
            )
            .distinct()
            .order_by(
                EngineEventRow.tenant_id,
                EngineEventRow.owner_id,
                EngineEventRow.application_id,
            )
        )
        return [(tenant, owner, app) for tenant, owner, app in self._session.execute(stmt)]

    def get_latest_aggregate_version(
        self,
        tenant_id: str,
        owner_id: str,
        application_id: str,
        aggregate_type: str,
        aggregate_id: str,
    ) -> int | None:
        stmt = (
            select(EngineEventRow.aggregate_version)
            .where(
                EngineEventRow.tenant_id == tenant_id,
                EngineEventRow.owner_id == owner_id,
                EngineEventRow.application_id == application_id,
                EngineEventRow.aggregate_type == aggregate_type,
                EngineEventRow.aggregate_id == aggregate_id,
            )
            .order_by(EngineEventRow.aggregate_version.desc())
            .limit(1)
        )
        return self._session.scalars(stmt).first()

    # ---------------------------------------------------------------- internal

    def _append_with_head(self, event: EngineEvent, head: EventStreamHeadRow) -> EngineEvent:
        validate_event_payload(event.event_type, event.schema_version, event.payload)
        self._assert_optimistic_concurrency(event)

        previous_hash = head.current_event_hash
        event_hash = compute_event_hash(event, previous_hash)

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

        # Advance the head atomically within the same transaction.
        head.last_global_position = row.global_position
        head.last_event_id = row.event_id
        head.current_event_hash = event_hash
        head.stream_version = head.stream_version + 1
        head.updated_at = row.recorded_at
        self._session.flush()
        return _row_to_event(row)

    def _lock_head(self, tenant_id: str, owner_id: str, application_id: str) -> EventStreamHeadRow:
        """Ensure the stream head exists and lock it FOR UPDATE.

        Race-safe creation: on PostgreSQL an INSERT ... ON CONFLICT DO NOTHING
        guarantees the row exists without aborting the transaction; the
        subsequent SELECT ... FOR UPDATE serializes concurrent writers of the
        same stream. SQLite serializes writers at the database level, so the
        FOR UPDATE clause is a harmless no-op there.
        """
        now = datetime.now(UTC)
        if self._is_postgres:
            self._session.execute(
                pg_insert(EventStreamHeadRow)
                .values(
                    tenant_id=tenant_id,
                    owner_id=owner_id,
                    application_id=application_id,
                    last_global_position=0,
                    last_event_id=None,
                    current_event_hash=None,
                    stream_version=0,
                    status=StreamStatus.ACTIVE.value,
                    updated_at=now,
                )
                .on_conflict_do_nothing(index_elements=["tenant_id", "owner_id", "application_id"])
            )
        else:
            existing = self._session.get(EventStreamHeadRow, (tenant_id, owner_id, application_id))
            if existing is None:
                self._session.add(
                    EventStreamHeadRow(
                        tenant_id=tenant_id,
                        owner_id=owner_id,
                        application_id=application_id,
                        last_global_position=0,
                        stream_version=0,
                        status=StreamStatus.ACTIVE.value,
                        updated_at=now,
                    )
                )
            self._session.flush()

        stmt = (
            select(EventStreamHeadRow)
            .where(
                EventStreamHeadRow.tenant_id == tenant_id,
                EventStreamHeadRow.owner_id == owner_id,
                EventStreamHeadRow.application_id == application_id,
            )
            .with_for_update()
        )
        head = self._session.scalars(stmt).first()
        if head is None:  # pragma: no cover - insert above guarantees existence
            raise RuntimeError("stream head disappeared after ensure")
        return head

    @staticmethod
    def _reject_if_quarantined(head: EventStreamHeadRow) -> None:
        if head.status == StreamStatus.QUARANTINED.value:
            raise StreamQuarantinedError(
                f"stream ({head.tenant_id}, {head.owner_id}, {head.application_id}) "
                f"is quarantined: {head.quarantine_reason or 'integrity break detected'}"
            )

    def _assert_optimistic_concurrency(self, event: EngineEvent) -> None:
        latest = self.get_latest_aggregate_version(
            event.tenant_id,
            event.owner_id,
            event.application_id,
            event.aggregate_type,
            event.aggregate_id,
        )
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
