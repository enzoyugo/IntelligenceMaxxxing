"""FastAPI dependencies wiring settings, database, auth and use cases."""

from typing import Annotated, cast

from fastapi import Depends, Header, Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from intelligence_maxxxing import API_VERSION
from intelligence_maxxxing.application.auth import AuthContext, AuthenticationService
from intelligence_maxxxing.application.ports import HealthSnapshotProviderPort
from intelligence_maxxxing.application.use_cases import (
    GetAuditUseCase,
    SubmitObservationUseCase,
)
from intelligence_maxxxing.application.use_cases.read_observations import (
    GetObservationUseCase,
    ListObservationsUseCase,
)
from intelligence_maxxxing.config import EngineSettings
from intelligence_maxxxing.infrastructure.health import (
    MeasuredHealthSnapshotProvider,
    SqlAlchemyDatabaseHealth,
)
from intelligence_maxxxing.infrastructure.repositories import SqlAlchemyUnitOfWork
from intelligence_maxxxing.infrastructure.repositories.identity import (
    SqlAlchemyIdentityStore,
)


def get_app_settings(request: Request) -> EngineSettings:
    return cast(EngineSettings, request.app.state.settings)


def get_database_engine(request: Request) -> Engine:
    return cast(Engine, request.app.state.db_engine)


def get_session_factory(request: Request) -> sessionmaker[Session]:
    return cast(sessionmaker[Session], request.app.state.session_factory)


def get_request_id(request: Request) -> str:
    return cast(str, request.state.request_id)


def get_database_health(request: Request) -> SqlAlchemyDatabaseHealth:
    return SqlAlchemyDatabaseHealth(get_database_engine(request))


def get_health_snapshot_provider(request: Request) -> HealthSnapshotProviderPort:
    return MeasuredHealthSnapshotProvider(get_database_health(request))


def get_auth_context(
    request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> AuthContext:
    """Resolve the authenticated identity. Deny-closed for protected routes."""
    session_factory = get_session_factory(request)
    with session_factory() as session:
        identity = SqlAlchemyIdentityStore(session)
        service = AuthenticationService(identity)
        context = service.authenticate(authorization, get_request_id(request))
        session.commit()
    return context


def get_submit_observation_use_case(request: Request) -> SubmitObservationUseCase:
    settings = get_app_settings(request)
    return SubmitObservationUseCase(
        uow=SqlAlchemyUnitOfWork(get_session_factory(request)),
        engine_version=settings.engine_version,
        api_version=API_VERSION,
        health_provider=get_health_snapshot_provider(request),
    )


def get_audit_use_case(request: Request) -> GetAuditUseCase:
    return GetAuditUseCase(SqlAlchemyUnitOfWork(get_session_factory(request)))


def get_observation_use_case(request: Request) -> GetObservationUseCase:
    return GetObservationUseCase(SqlAlchemyUnitOfWork(get_session_factory(request)))


def get_list_observations_use_case(request: Request) -> ListObservationsUseCase:
    return ListObservationsUseCase(SqlAlchemyUnitOfWork(get_session_factory(request)))


# Convenience aliases used by route signatures.
AuthDep = Annotated[AuthContext, Depends(get_auth_context)]
