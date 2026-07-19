"""SQLAlchemy idempotency ledger (Stage 1: composite scope).

Effective unique key: (application_id, owner_id, action, idempotency_key).
Two applications can reuse the same key without collision. Concurrent
inserts of the same scope raise IntegrityError, which the unit of work
translates into IdempotencyRaceDetected for deterministic resolution.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from intelligence_maxxxing.application.ports import IdempotencyRecord, IdempotencyStorePort
from intelligence_maxxxing.infrastructure.database.tables import IdempotencyKeyRow


class SqlAlchemyIdempotencyStore(IdempotencyStorePort):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(
        self, application_id: str, owner_id: str, action: str, idempotency_key: str
    ) -> IdempotencyRecord | None:
        stmt = select(IdempotencyKeyRow).where(
            IdempotencyKeyRow.application_id == application_id,
            IdempotencyKeyRow.owner_id == owner_id,
            IdempotencyKeyRow.action == action,
            IdempotencyKeyRow.idempotency_key == idempotency_key,
        )
        row = self._session.scalars(stmt).first()
        if row is None:
            return None
        return IdempotencyRecord(
            tenant_id=row.tenant_id,
            owner_id=row.owner_id,
            application_id=row.application_id,
            actor_id=row.actor_id,
            action=row.action,
            idempotency_key=row.idempotency_key,
            payload_hash=row.payload_hash,
            observation_id=row.observation_id,
            event_id=row.event_id,
            audit_id=row.audit_id,
        )

    def put(self, record: IdempotencyRecord) -> None:
        self._session.add(
            IdempotencyKeyRow(
                tenant_id=record.tenant_id,
                owner_id=record.owner_id,
                application_id=record.application_id,
                actor_id=record.actor_id,
                action=record.action,
                idempotency_key=record.idempotency_key,
                payload_hash=record.payload_hash,
                observation_id=record.observation_id,
                event_id=record.event_id,
                audit_id=record.audit_id,
            )
        )
