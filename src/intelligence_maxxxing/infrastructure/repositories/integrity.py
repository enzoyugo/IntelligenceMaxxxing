"""SQLAlchemy integrity store: stream heads and integrity checkpoints.

Stream heads are the transactional per-stream chain heads that make concurrent
appends form a single chain (see the event store). Integrity checkpoints record
the last reliably verified point of a stream so INCREMENTAL verification can
resume with a trusted anchor.

Neither structure is ledger evidence: the runtime may advance them through the
methods here, but it never rewrites events/audits, and a quarantine is only
released through the governed admin path (`release_stream`).
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from intelligence_maxxxing.application.ports import (
    IntegrityStorePort,
    IntegrityStreamCheckpoint,
    StreamHead,
    StreamStatus,
)
from intelligence_maxxxing.infrastructure.database.tables import (
    EventStreamHeadRow,
    IntegrityCheckpointRow,
)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _as_utc_opt(value: datetime | None) -> datetime | None:
    return None if value is None else _as_utc(value)


def _head_to_model(row: EventStreamHeadRow) -> StreamHead:
    return StreamHead(
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        last_global_position=row.last_global_position,
        last_event_id=row.last_event_id,
        current_event_hash=row.current_event_hash,
        stream_version=row.stream_version,
        status=row.status,
        quarantine_reason=row.quarantine_reason,
        broken_event_id=row.broken_event_id,
        quarantined_at=_as_utc_opt(row.quarantined_at),
        quarantine_audit_id=row.quarantine_audit_id,
        updated_at=_as_utc(row.updated_at),
    )


def _checkpoint_to_model(row: IntegrityCheckpointRow) -> IntegrityStreamCheckpoint:
    return IntegrityStreamCheckpoint(
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        last_verified_global_position=row.last_verified_global_position,
        last_verified_event_id=row.last_verified_event_id,
        last_verified_hash=row.last_verified_hash,
        verified_at=_as_utc(row.verified_at),
        status=row.status,
    )


class SqlAlchemyIntegrityStore(IntegrityStorePort):
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------ stream heads

    def get_stream_head(
        self, tenant_id: str, owner_id: str, application_id: str
    ) -> StreamHead | None:
        row = self._session.get(EventStreamHeadRow, (tenant_id, owner_id, application_id))
        return None if row is None else _head_to_model(row)

    def list_stream_heads(self) -> Sequence[StreamHead]:
        stmt = select(EventStreamHeadRow).order_by(
            EventStreamHeadRow.tenant_id,
            EventStreamHeadRow.owner_id,
            EventStreamHeadRow.application_id,
        )
        return [_head_to_model(row) for row in self._session.scalars(stmt)]

    def quarantine_stream(
        self,
        tenant_id: str,
        owner_id: str,
        application_id: str,
        *,
        reason: str,
        broken_event_id: str,
        audit_id: str,
        detected_at: datetime,
    ) -> None:
        row = self._session.get(EventStreamHeadRow, (tenant_id, owner_id, application_id))
        if row is None:
            # A violation on a stream that somehow has no head: create a
            # quarantined head so future writes are still rejected.
            row = EventStreamHeadRow(
                tenant_id=tenant_id,
                owner_id=owner_id,
                application_id=application_id,
                last_global_position=0,
                stream_version=0,
                updated_at=detected_at,
            )
            self._session.add(row)
        row.status = StreamStatus.QUARANTINED.value
        row.quarantine_reason = reason
        row.broken_event_id = broken_event_id
        row.quarantine_audit_id = audit_id
        row.quarantined_at = detected_at
        row.updated_at = detected_at

    def release_stream(self, tenant_id: str, owner_id: str, application_id: str) -> None:
        row = self._session.get(EventStreamHeadRow, (tenant_id, owner_id, application_id))
        if row is None:
            return
        row.status = StreamStatus.ACTIVE.value
        row.quarantine_reason = None
        row.broken_event_id = None
        row.quarantine_audit_id = None
        row.quarantined_at = None
        row.updated_at = datetime.now(UTC)

    # ------------------------------------------------------ integrity checkpoints

    def get_integrity_checkpoint(
        self, tenant_id: str, owner_id: str, application_id: str
    ) -> IntegrityStreamCheckpoint | None:
        row = self._session.get(IntegrityCheckpointRow, (tenant_id, owner_id, application_id))
        return None if row is None else _checkpoint_to_model(row)

    def save_integrity_checkpoint(self, checkpoint: IntegrityStreamCheckpoint) -> None:
        row = self._session.get(
            IntegrityCheckpointRow,
            (checkpoint.tenant_id, checkpoint.owner_id, checkpoint.application_id),
        )
        if row is None:
            self._session.add(
                IntegrityCheckpointRow(
                    tenant_id=checkpoint.tenant_id,
                    owner_id=checkpoint.owner_id,
                    application_id=checkpoint.application_id,
                    last_verified_global_position=checkpoint.last_verified_global_position,
                    last_verified_event_id=checkpoint.last_verified_event_id,
                    last_verified_hash=checkpoint.last_verified_hash,
                    verified_at=checkpoint.verified_at,
                    status=checkpoint.status,
                )
            )
            return
        row.last_verified_global_position = checkpoint.last_verified_global_position
        row.last_verified_event_id = checkpoint.last_verified_event_id
        row.last_verified_hash = checkpoint.last_verified_hash
        row.verified_at = checkpoint.verified_at
        row.status = checkpoint.status
