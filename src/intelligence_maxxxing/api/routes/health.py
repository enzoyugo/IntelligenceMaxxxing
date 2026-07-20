"""Health endpoints.

- GET /health/live          : process alive (no auth, no DB)
- GET /health/ready         : can serve traffic (DB reachable; no secrets)
- GET /api/v1/health        : authenticated detailed health (measured components)
"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse

from intelligence_maxxxing.api.dependencies import (
    AuthDep,
    get_app_settings,
    get_database_health,
    get_health_snapshot_provider,
    get_request_id,
)
from intelligence_maxxxing.api.envelope import build_meta, success_envelope
from intelligence_maxxxing.application.ports import HealthSnapshotProviderPort
from intelligence_maxxxing.config import EngineSettings, get_settings
from intelligence_maxxxing.contracts.api.envelope import ApiResponseEnvelope
from intelligence_maxxxing.contracts.api.health import HealthData
from intelligence_maxxxing.domain.common.health import (
    ComponentHealth,
    HealthState,
    HealthStatus,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v1 import FORMULA_ID as V1_ID
from intelligence_maxxxing.domain_packs.life.wellbeing_v1 import FORMULA_VERSION as V1_VER
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.registry import FORMULA_ID as V2_ID
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.registry import (
    FORMULA_VERSION as V2_VER,
)
from intelligence_maxxxing.governance import verify_manifest
from intelligence_maxxxing.governance.manifest import find_constitutional_dir
from intelligence_maxxxing.infrastructure.health import SqlAlchemyDatabaseHealth
from intelligence_maxxxing import API_VERSION

router = APIRouter()
public_router = APIRouter()


def _commit_sha(settings: EngineSettings) -> str | None:
    if settings.engine_commit_sha:
        return settings.engine_commit_sha
    try:
        import subprocess
        from pathlib import Path

        root = Path(__file__).resolve().parents[4]
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return out.strip() or None
    except Exception:
        return None


def _migration_revision() -> str | None:
    try:
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine

        settings = get_settings()
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            rev = ctx.get_current_revision()
        engine.dispose()
        return rev
    except Exception:
        return None


@public_router.get("/health/live")
def live(
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
) -> dict[str, object]:
    """Process is alive. Includes non-secret build identity; never secrets."""
    return {
        "status": "ok",
        "service": "IntelligenceMaxxxing",
        "commit_sha": _commit_sha(settings),
        "api_version": API_VERSION,
        "engine_version": settings.engine_version,
        "wellbeing": {
            "active": f"{V1_ID}@{V1_VER}",
            "shadow": f"{V2_ID}@{V2_VER}",
        },
    }


@public_router.get("/health/ready")
def ready(
    database_health: Annotated[SqlAlchemyDatabaseHealth, Depends(get_database_health)],
) -> JSONResponse:
    """Basic readiness: database reachable. No sensitive detail."""
    db = database_health.check()
    if db.state is HealthState.HEALTHY:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ready"})
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "not_ready"},
    )


def _manifest_health() -> ComponentHealth:
    try:
        constitutional_dir = find_constitutional_dir(Path.cwd())
    except FileNotFoundError:
        return ComponentHealth(
            component="constitutional_manifest",
            state=HealthState.DEGRADED,
            detail="docs/constitutional not found from working directory",
        )
    result = verify_manifest(constitutional_dir)
    if result.ok:
        return ComponentHealth(component="constitutional_manifest", state=HealthState.HEALTHY)
    return ComponentHealth(
        component="constitutional_manifest",
        state=HealthState.UNHEALTHY,
        detail=(
            f"mismatched={list(result.mismatched)} missing={list(result.missing_files)} "
            f"unlisted={list(result.unlisted_files)}"
        ),
    )


@router.get("/health", response_model=ApiResponseEnvelope)
def get_health(
    auth: AuthDep,
    response: Response,
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    health_provider: Annotated[HealthSnapshotProviderPort, Depends(get_health_snapshot_provider)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> ApiResponseEnvelope:
    """Authenticated detailed health. Requires a valid credential (any scope)."""
    _ = auth  # authentication is the gate; no specific scope required
    snapshot = health_provider.capture()
    measured = tuple(
        ComponentHealth(component=c.component, state=c.state, detail=c.detail)
        for c in snapshot.checked_components()
    )
    # Include the separate manifest probe for the detailed view.
    measured = (*measured, _manifest_health())
    status_agg = HealthStatus.aggregate(measured)

    if status_agg.status is HealthState.UNHEALTHY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    db_state = next(
        (c.state.value for c in status_agg.components if c.component == "database"),
        "unknown",
    )
    data = HealthData(
        status=status_agg.status.value,
        service="IntelligenceMaxxxing Engine",
        engine_version=settings.engine_version,
        constitution_version=settings.constitution_version,
        commit_sha=_commit_sha(settings),
        api_version=API_VERSION,
        database="reachable" if db_state == HealthState.HEALTHY.value else db_state,
        migration_revision=_migration_revision(),
        wellbeing_active=f"{V1_ID}@{V1_VER}",
        wellbeing_shadow=f"{V2_ID}@{V2_VER}",
    )
    meta = build_meta(
        request_id=request_id,
        engine_version=settings.engine_version,
        health={c.component: c.state.value for c in status_agg.components},
    )
    return success_envelope(data.model_dump(), meta)
