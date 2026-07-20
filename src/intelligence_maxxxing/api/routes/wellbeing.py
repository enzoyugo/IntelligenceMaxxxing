"""Wellbeing Intelligence endpoints — V1 ACTIVE default, V2 SHADOW opt-in."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from intelligence_maxxxing.api.dependencies import (
    AuthDep,
    get_app_settings,
    get_request_id,
    get_wellbeing_service,
)
from intelligence_maxxxing.api.envelope import build_meta, success_envelope
from intelligence_maxxxing.application.auth import require_scope
from intelligence_maxxxing.application.errors import UnknownFormulaError
from intelligence_maxxxing.application.use_cases.wellbeing import WellbeingService
from intelligence_maxxxing.config import EngineSettings
from intelligence_maxxxing.contracts.api.envelope import ApiResponseEnvelope
from intelligence_maxxxing.contracts.api.wellbeing import (
    WellbeingCurrentData,
    WellbeingFeedbackRequest,
    WellbeingHistoryData,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v1 import FORMULA_ID as V1_ID
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.registry import FORMULA_ID as V2_ID
from intelligence_maxxxing.permissions import PermissionScope

router = APIRouter(prefix="/wellbeing")


@router.get("/current", response_model=ApiResponseEnvelope)
def get_current_wellbeing(
    auth: AuthDep,
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    service: Annotated[WellbeingService, Depends(get_wellbeing_service)],
    request_id: Annotated[str, Depends(get_request_id)],
    window_days: Annotated[int, Query(ge=3, le=90)] = 14,
    formula_id: Annotated[str, Query()] = V1_ID,
) -> ApiResponseEnvelope:
    require_scope(auth, PermissionScope.READ_INTELLIGENCE)
    if formula_id not in {V1_ID, V2_ID}:
        raise UnknownFormulaError(
            f"Unknown formula_id '{formula_id}'. Allowed: {V1_ID} (ACTIVE), {V2_ID} (SHADOW)."
        )
    snapshot = service.get_current(auth, window_days=window_days, formula_id=formula_id)
    return success_envelope(
        WellbeingCurrentData(snapshot=snapshot).model_dump(),
        build_meta(request_id, settings.engine_version, domain_pack="life"),
    )


@router.get("/shadow/compare", response_model=ApiResponseEnvelope)
def compare_shadow(
    auth: AuthDep,
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    service: Annotated[WellbeingService, Depends(get_wellbeing_service)],
    request_id: Annotated[str, Depends(get_request_id)],
    window_days: Annotated[int, Query(ge=3, le=90)] = 14,
) -> ApiResponseEnvelope:
    """Run V1 ACTIVE and V2 SHADOW side-by-side. Never promotes V2."""
    require_scope(auth, PermissionScope.READ_INTELLIGENCE)
    data = service.compare_shadow(auth, window_days=window_days)
    return success_envelope(
        data.model_dump(),
        build_meta(request_id, settings.engine_version, domain_pack="life"),
    )


@router.get("/history", response_model=ApiResponseEnvelope)
def get_wellbeing_history(
    auth: AuthDep,
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    service: Annotated[WellbeingService, Depends(get_wellbeing_service)],
    request_id: Annotated[str, Depends(get_request_id)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponseEnvelope:
    require_scope(auth, PermissionScope.READ_INTELLIGENCE)
    items = service.list_history(auth, limit=limit)
    return success_envelope(
        WellbeingHistoryData(items=items).model_dump(),
        build_meta(request_id, settings.engine_version, domain_pack="life"),
    )


@router.get("/explanation", response_model=ApiResponseEnvelope)
def get_wellbeing_explanation(
    auth: AuthDep,
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    service: Annotated[WellbeingService, Depends(get_wellbeing_service)],
    request_id: Annotated[str, Depends(get_request_id)],
    score_snapshot_id: Annotated[str | None, Query()] = None,
    formula_id: Annotated[str, Query()] = V1_ID,
) -> ApiResponseEnvelope:
    require_scope(auth, PermissionScope.READ_INTELLIGENCE)
    snapshot = service.get_explanation(auth, score_snapshot_id=score_snapshot_id, formula_id=formula_id)
    return success_envelope(
        WellbeingCurrentData(snapshot=snapshot).model_dump(),
        build_meta(request_id, settings.engine_version, domain_pack="life"),
    )


@router.get("/formula", response_model=ApiResponseEnvelope)
def get_wellbeing_formula(
    auth: AuthDep,
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    service: Annotated[WellbeingService, Depends(get_wellbeing_service)],
    request_id: Annotated[str, Depends(get_request_id)],
    formula_id: Annotated[str, Query()] = V1_ID,
) -> ApiResponseEnvelope:
    require_scope(auth, PermissionScope.READ_INTELLIGENCE)
    formula = service.get_formula(formula_id=formula_id)
    return success_envelope(
        formula.model_dump(),
        build_meta(request_id, settings.engine_version, domain_pack="life"),
    )


@router.post("/feedback", response_model=ApiResponseEnvelope)
def post_wellbeing_feedback(
    body: WellbeingFeedbackRequest,
    auth: AuthDep,
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    service: Annotated[WellbeingService, Depends(get_wellbeing_service)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> ApiResponseEnvelope:
    require_scope(auth, PermissionScope.SUBMIT_OBSERVATION)
    result = service.submit_feedback(
        auth,
        rating=body.rating,
        score_snapshot_id=body.score_snapshot_id,
        note=body.note,
    )
    return success_envelope(
        result.model_dump(),
        build_meta(request_id, settings.engine_version, domain_pack="life"),
    )
