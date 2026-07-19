"""FastAPI dependencies wiring settings, database and use cases."""

from typing import cast

from fastapi import Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from intelligence_maxxxing import API_VERSION
from intelligence_maxxxing.application.use_cases import (
    GetAuditUseCase,
    SubmitObservationUseCase,
)
from intelligence_maxxxing.config import EngineSettings
from intelligence_maxxxing.infrastructure.health import SqlAlchemyDatabaseHealth
from intelligence_maxxxing.infrastructure.repositories import SqlAlchemyUnitOfWork


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


def get_submit_observation_use_case(request: Request) -> SubmitObservationUseCase:
    settings = get_app_settings(request)
    uow = SqlAlchemyUnitOfWork(get_session_factory(request))
    return SubmitObservationUseCase(
        uow=uow,
        engine_version=settings.engine_version,
        api_version=API_VERSION,
    )


def get_audit_use_case(request: Request) -> GetAuditUseCase:
    return GetAuditUseCase(SqlAlchemyUnitOfWork(get_session_factory(request)))
