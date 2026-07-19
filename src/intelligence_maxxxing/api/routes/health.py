"""GET /api/v1/health with real component checks (API, database, manifest)."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from intelligence_maxxxing.api.dependencies import (
    get_app_settings,
    get_database_health,
    get_request_id,
)
from intelligence_maxxxing.api.envelope import build_meta, success_envelope
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
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    database_health: Annotated[SqlAlchemyDatabaseHealth, Depends(get_database_health)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> ApiResponseEnvelope:
    api_component = ComponentHealth(component="api", state=HealthState.HEALTHY)
    db_component = database_health.check()
    manifest_component = _manifest_health()

    status = HealthStatus.aggregate((api_component, db_component, manifest_component))

    data = HealthData(
        status=status.status.value,
        service="IntelligenceMaxxxing Engine",
        engine_version=settings.engine_version,
        constitution_version=settings.constitution_version,
    )
    meta = build_meta(
        request_id=request_id,
        engine_version=settings.engine_version,
        health={c.component: c.state.value for c in status.components},
    )
    return success_envelope(data.model_dump(), meta)
