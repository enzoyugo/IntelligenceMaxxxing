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
from intelligence_maxxxing.application.use_cases.epistemic import (
    ActivateHypothesisUseCase,
    EvaluateExperimentUseCase,
    GetCurrentBeliefUseCase,
    GetExperimentProgressUseCase,
    GetExperimentUseCase,
    GetHypothesisUseCase,
    ListBeliefsUseCase,
    ListHypothesesUseCase,
    ListLearningUseCase,
    ProposeHypothesisUseCase,
    RetireHypothesisUseCase,
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


def _uow(request: Request) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(get_session_factory(request))


def get_submit_observation_use_case(request: Request) -> SubmitObservationUseCase:
    settings = get_app_settings(request)
    return SubmitObservationUseCase(
        uow=_uow(request),
        engine_version=settings.engine_version,
        api_version=API_VERSION,
        health_provider=get_health_snapshot_provider(request),
    )


def get_audit_use_case(request: Request) -> GetAuditUseCase:
    return GetAuditUseCase(_uow(request))


def get_observation_use_case(request: Request) -> GetObservationUseCase:
    return GetObservationUseCase(_uow(request))


def get_list_observations_use_case(request: Request) -> ListObservationsUseCase:
    return ListObservationsUseCase(_uow(request))


def get_propose_hypothesis_use_case(request: Request) -> ProposeHypothesisUseCase:
    settings = get_app_settings(request)
    return ProposeHypothesisUseCase(
        uow=_uow(request),
        engine_version=settings.engine_version,
        api_version=API_VERSION,
        health_provider=get_health_snapshot_provider(request),
    )


def get_activate_hypothesis_use_case(request: Request) -> ActivateHypothesisUseCase:
    settings = get_app_settings(request)
    return ActivateHypothesisUseCase(
        uow=_uow(request),
        engine_version=settings.engine_version,
        api_version=API_VERSION,
        health_provider=get_health_snapshot_provider(request),
    )


def get_retire_hypothesis_use_case(request: Request) -> RetireHypothesisUseCase:
    settings = get_app_settings(request)
    return RetireHypothesisUseCase(
        uow=_uow(request),
        engine_version=settings.engine_version,
        api_version=API_VERSION,
        health_provider=get_health_snapshot_provider(request),
    )


def get_evaluate_experiment_use_case(request: Request) -> EvaluateExperimentUseCase:
    settings = get_app_settings(request)
    return EvaluateExperimentUseCase(
        uow=_uow(request),
        engine_version=settings.engine_version,
        api_version=API_VERSION,
        health_provider=get_health_snapshot_provider(request),
    )


def get_hypothesis_use_case(request: Request) -> GetHypothesisUseCase:
    return GetHypothesisUseCase(_uow(request))


def get_list_hypotheses_use_case(request: Request) -> ListHypothesesUseCase:
    return ListHypothesesUseCase(_uow(request))


def get_experiment_use_case(request: Request) -> GetExperimentUseCase:
    return GetExperimentUseCase(_uow(request))


def get_experiment_progress_use_case(request: Request) -> GetExperimentProgressUseCase:
    return GetExperimentProgressUseCase(_uow(request))


def get_current_belief_use_case(request: Request) -> GetCurrentBeliefUseCase:
    return GetCurrentBeliefUseCase(_uow(request))


def get_list_beliefs_use_case(request: Request) -> ListBeliefsUseCase:
    return ListBeliefsUseCase(_uow(request))


def get_list_learning_use_case(request: Request) -> ListLearningUseCase:
    return ListLearningUseCase(_uow(request))


def get_wellbeing_service(request: Request) -> "WellbeingService":
    from intelligence_maxxxing.application.use_cases.wellbeing import WellbeingService

    return WellbeingService(
        uow=_uow(request),
        session_factory=get_session_factory(request),
    )


# Convenience aliases used by route signatures.
AuthDep = Annotated[AuthContext, Depends(get_auth_context)]
