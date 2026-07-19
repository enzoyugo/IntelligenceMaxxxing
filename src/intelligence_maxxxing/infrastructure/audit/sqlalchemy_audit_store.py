"""SQLAlchemy implementation of the append-only audit store."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from intelligence_maxxxing.application.ports import AuditStorePort
from intelligence_maxxxing.domain.audit.models import Actor, AuditRecord
from intelligence_maxxxing.domain.common.base import MetadataValue
from intelligence_maxxxing.domain.common.epistemic import ActorType
from intelligence_maxxxing.infrastructure.database.tables import AuditRecordRow


def _as_utc(value: datetime) -> datetime:
    """Timestamps are stored in UTC; SQLite drops tzinfo, so restore it on read."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _row_to_record(row: AuditRecordRow) -> AuditRecord:
    health_state: dict[str, MetadataValue] = {
        key: value if isinstance(value, str | int | float | bool) or value is None else str(value)
        for key, value in row.health_state.items()
    }
    return AuditRecord(
        audit_id=row.audit_id,
        request_id=row.request_id,
        engine_version=row.engine_version,
        api_version=row.api_version,
        schema_version=row.schema_version,
        domain_pack=row.domain_pack,
        actor=Actor(actor_type=ActorType(row.actor_type), actor_id=row.actor_id),
        action=row.action,
        input_object_ids=tuple(row.input_object_ids),
        output_object_ids=tuple(row.output_object_ids),
        event_ids=tuple(row.event_ids),
        timestamp=_as_utc(row.timestamp),
        health_state=health_state,
    )


class SqlAlchemyAuditStore(AuditStorePort):
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, record: AuditRecord) -> None:
        row = AuditRecordRow(
            audit_id=record.audit_id,
            request_id=record.request_id,
            engine_version=record.engine_version,
            api_version=record.api_version,
            schema_version=record.schema_version,
            domain_pack=record.domain_pack,
            actor_type=record.actor.actor_type.value,
            actor_id=record.actor.actor_id,
            action=record.action,
            input_object_ids=list(record.input_object_ids),
            output_object_ids=list(record.output_object_ids),
            event_ids=list(record.event_ids),
            timestamp=record.timestamp,
            health_state=dict(record.health_state),
        )
        self._session.add(row)

    def get_by_audit_id(self, audit_id: str) -> AuditRecord | None:
        row = self._session.get(AuditRecordRow, audit_id)
        return _row_to_record(row) if row is not None else None
