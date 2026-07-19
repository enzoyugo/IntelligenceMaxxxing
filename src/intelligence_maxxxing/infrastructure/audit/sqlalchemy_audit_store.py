"""SQLAlchemy implementation of the append-only audit store.

Reads are owner-scoped: an application cannot retrieve another owner's audit
by guessing its id.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from intelligence_maxxxing.application.ports import AuditStorePort
from intelligence_maxxxing.domain.audit.models import Actor, AuditRecord
from intelligence_maxxxing.domain.common.epistemic import ActorType
from intelligence_maxxxing.infrastructure.database.tables import AuditRecordRow


def _as_utc(value: datetime) -> datetime:
    """Timestamps are stored in UTC; SQLite drops tzinfo, so restore it on read."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _row_to_record(row: AuditRecordRow) -> AuditRecord:
    return AuditRecord(
        audit_id=row.audit_id,
        request_id=row.request_id,
        engine_version=row.engine_version,
        api_version=row.api_version,
        schema_version=row.schema_version,
        domain_pack=row.domain_pack,
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        actor=Actor(actor_type=ActorType(row.actor_type), actor_id=row.actor_id),
        action=row.action,
        input_object_ids=tuple(row.input_object_ids),
        output_object_ids=tuple(row.output_object_ids),
        event_ids=tuple(row.event_ids),
        timestamp=_as_utc(row.timestamp),
        health_state=dict(row.health_state),
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
            tenant_id=record.tenant_id,
            owner_id=record.owner_id,
            application_id=record.application_id,
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

    def get_by_audit_id(self, owner_id: str, audit_id: str) -> AuditRecord | None:
        stmt = select(AuditRecordRow).where(
            AuditRecordRow.audit_id == audit_id,
            AuditRecordRow.owner_id == owner_id,
        )
        row = self._session.scalars(stmt).first()
        return _row_to_record(row) if row is not None else None
