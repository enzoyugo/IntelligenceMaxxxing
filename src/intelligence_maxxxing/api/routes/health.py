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
from intelligence_maxxxing.config import EngineSettings
from intelligence_maxxxing.contracts.api.envelope import ApiResponseEnvelope
from intelligence_maxxxing.contracts.api.health import HealthData
from intelligence_maxxxing.domain.common.health import (
    ComponentHealth,
    HealthState,
    HealthStatus,
)
from intelligence_maxxxing.governance import verify_manifest
from intelligence_maxxxing.governance.manifest import find_constitutional_dir
from intelligence_maxxxing.infrastructure.health import SqlAlchemyDatabaseHealth

router = APIRouter()
public_router = APIRouter()


@public_router.get("/health/live")
def live() -> dict[str, str]:
    """Process is alive. Never touches the database or secrets."""
    return {"status": "ok"}


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

    data = HealthData(
        status=status_agg.status.value,
        service="IntelligenceMaxxxing Engine",
        engine_version=settings.engine_version,
        constitution_version=settings.constitution_version,
    )
    meta = build_meta(
        request_id=request_id,
        engine_version=settings.engine_version,
        health={c.component: c.state.value for c in status_agg.components},
    )
    return success_envelope(data.model_dump(), meta)
