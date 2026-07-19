"""SQLAlchemy unit of work: one transaction per write path.

Translates unique-constraint races on the composite idempotency key into the
typed IdempotencyRaceDetected signal so the use case can resolve them
deterministically (never a raw IntegrityError / HTTP 500).
"""

from types import TracebackType

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from intelligence_maxxxing.application.errors import IdempotencyRaceDetected
from intelligence_maxxxing.application.ports import UnitOfWorkPort
from intelligence_maxxxing.infrastructure.audit import SqlAlchemyAuditStore
from intelligence_maxxxing.infrastructure.event_store import SqlAlchemyEventStore
from intelligence_maxxxing.infrastructure.repositories.idempotency import (
    SqlAlchemyIdempotencyStore,
)
from intelligence_maxxxing.infrastructure.repositories.identity import (
    SqlAlchemyIdentityStore,
)
from intelligence_maxxxing.infrastructure.repositories.integrity import (
    SqlAlchemyIntegrityStore,
)
from intelligence_maxxxing.infrastructure.repositories.projections import (
    SqlAlchemyProjectionStore,
)


class SqlAlchemyUnitOfWork(UnitOfWorkPort):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self._session = self._session_factory()
        self.events = SqlAlchemyEventStore(self._session)
        self.audits = SqlAlchemyAuditStore(self._session)
        self.idempotency = SqlAlchemyIdempotencyStore(self._session)
        self.identity = SqlAlchemyIdentityStore(self._session)
        self.projections = SqlAlchemyProjectionStore(self._session)
        self.integrity = SqlAlchemyIntegrityStore(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self._session is not None
        try:
            if exc_type is not None:
                self._session.rollback()
        finally:
            self._session.close()
            self._session = None

    def commit(self) -> None:
        assert self._session is not None
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            message = str(exc.orig) if exc.orig is not None else str(exc)
            if "uq_idempotency_scope_key" in message or "idempotency" in message.lower():
                raise IdempotencyRaceDetected(
                    "concurrent request with the same idempotency scope committed first"
                ) from exc
            raise
