"""FastAPI application factory for the IntelligenceMaxxxing Engine."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from intelligence_maxxxing import API_VERSION, ENGINE_VERSION
from intelligence_maxxxing.api.errors import register_error_handlers
from intelligence_maxxxing.api.middleware import register_middleware
from intelligence_maxxxing.api.routes import audits, experiments, health, hypotheses, observations
from intelligence_maxxxing.config import EngineSettings, get_settings
from intelligence_maxxxing.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from intelligence_maxxxing.observability import configure_logging

API_PREFIX = f"/api/{API_VERSION}"


def create_app(settings: EngineSettings | None = None) -> FastAPI:
    app_settings = settings if settings is not None else get_settings()
    configure_logging(app_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        app.state.db_engine.dispose()

    app = FastAPI(
        title="IntelligenceMaxxxing Engine",
        version=ENGINE_VERSION,
        description=(
            "Constitutionally governed, application-agnostic intelligence backend. "
            "Applications are external clients and communicate only through this API."
        ),
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.db_engine = create_database_engine(app_settings.database_url)
    app.state.session_factory = create_session_factory(app.state.db_engine)

    register_middleware(app)
    register_error_handlers(app)

    # Public liveness/readiness (no auth, no sensitive detail).
    app.include_router(health.public_router, tags=["health"])

    api_v1 = APIRouter(prefix=API_PREFIX)
    api_v1.include_router(health.router, tags=["health"])
    api_v1.include_router(observations.router, tags=["observations"])
    api_v1.include_router(hypotheses.router, tags=["hypotheses"])
    api_v1.include_router(experiments.router, tags=["experiments"])
    api_v1.include_router(audits.router, tags=["audits"])
    app.include_router(api_v1)

    return app
