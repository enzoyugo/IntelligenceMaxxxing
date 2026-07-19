"""SQLAlchemy unit of work: one transaction per write path."""

from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from intelligence_maxxxing.application.ports import UnitOfWorkPort
from intelligence_maxxxing.infrastructure.audit import SqlAlchemyAuditStore
from intelligence_maxxxing.infrastructure.event_store import SqlAlchemyEventStore
from intelligence_maxxxing.infrastructure.repositories.idempotency import (
    SqlAlchemyIdempotencyStore,
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
        self._session.commit()
