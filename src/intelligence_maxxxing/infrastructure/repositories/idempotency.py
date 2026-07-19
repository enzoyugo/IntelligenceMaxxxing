"""SQLAlchemy idempotency ledger."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from intelligence_maxxxing.application.ports import IdempotencyRecord, IdempotencyStorePort
from intelligence_maxxxing.infrastructure.database.tables import IdempotencyKeyRow


class SqlAlchemyIdempotencyStore(IdempotencyStorePort):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, scope: str, idempotency_key: str) -> IdempotencyRecord | None:
        stmt = select(IdempotencyKeyRow).where(
            IdempotencyKeyRow.scope == scope,
            IdempotencyKeyRow.idempotency_key == idempotency_key,
        )
        row = self._session.scalars(stmt).first()
        if row is None:
            return None
        return IdempotencyRecord(
            scope=row.scope,
            idempotency_key=row.idempotency_key,
            payload_hash=row.payload_hash,
            observation_id=row.observation_id,
            event_id=row.event_id,
            audit_id=row.audit_id,
        )

    def put(self, record: IdempotencyRecord) -> None:
        self._session.add(
            IdempotencyKeyRow(
                scope=record.scope,
                idempotency_key=record.idempotency_key,
                payload_hash=record.payload_hash,
                observation_id=record.observation_id,
                event_id=record.event_id,
                audit_id=record.audit_id,
            )
        )
