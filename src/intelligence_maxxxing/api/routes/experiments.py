"""Experiment endpoints (Stage 3: evaluate, read progress)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status

from intelligence_maxxxing.api.dependencies import (
    AuthDep,
    get_app_settings,
    get_evaluate_experiment_use_case,
    get_experiment_progress_use_case,
    get_experiment_use_case,
    get_request_id,
)
from intelligence_maxxxing.api.envelope import build_meta, success_envelope
from intelligence_maxxxing.application.auth import require_scope
from intelligence_maxxxing.application.use_cases.epistemic import (
    EvaluateExperimentCommand,
    EvaluateExperimentUseCase,
    GetExperimentProgressUseCase,
    GetExperimentUseCase,
)
from intelligence_maxxxing.config import EngineSettings
from intelligence_maxxxing.contracts.api.envelope import ApiResponseEnvelope
from intelligence_maxxxing.contracts.api.experiments import (
    EvaluateExperimentData,
    EvaluateExperimentRequest,
    ExperimentProgressView,
    ExperimentView,
)
from intelligence_maxxxing.permissions import PermissionScope

router = APIRouter()


@router.get("/experiments/{experiment_id}", response_model=ApiResponseEnvelope)
def get_experiment(
    experiment_id: str,
    auth: AuthDep,
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    use_case: Annotated[GetExperimentUseCase, Depends(get_experiment_use_case)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> ApiResponseEnvelope:
    require_scope(auth, PermissionScope.READ_HYPOTHESIS)
    row = use_case.execute(experiment_id, auth)
    data = ExperimentView(
        experiment_id=row.experiment_id,
        hypothesis_id=row.hypothesis_id,
        protocol_version=row.protocol_version,
        analysis_method=row.analysis_method,
        baseline_cutoff=row.baseline_cutoff.isoformat(),
        prospective_start=row.prospective_start.isoformat(),
        prospective_target=row.prospective_target,
        maximum_window_days=row.maximum_window_days,
        minimum_group_size=row.minimum_group_size,
        minimum_meaningful_difference=row.minimum_meaningful_difference,
        sleep_threshold_hours=row.sleep_threshold_hours,
        random_seed_policy=row.random_seed_policy,
        status=row.status,
        pre_registered_at=row.pre_registered_at.isoformat(),
        audit_id=row.audit_id,
        event_id=row.event_id,
    )
    meta = build_meta(
        request_id=request_id,
        engine_version=settings.engine_version,
        domain_pack="life",
        audit_id=row.audit_id,
    )
    return success_envelope(data.model_dump(), meta)


@router.get("/experiments/{experiment_id}/progress", response_model=ApiResponseEnvelope)
def get_experiment_progress(
    experiment_id: str,
    auth: AuthDep,
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    use_case: Annotated[GetExperimentProgressUseCase, Depends(get_experiment_progress_use_case)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> ApiResponseEnvelope:
    require_scope(auth, PermissionScope.READ_HYPOTHESIS)
    row = use_case.execute(experiment_id, auth)
    data = ExperimentProgressView(
        experiment_id=row.experiment_id,
        hypothesis_id=row.hypothesis_id,
        baseline_eligible=row.baseline_eligible,
        baseline_sufficient=row.baseline_sufficient,
        baseline_below=row.baseline_below,
        prospective_eligible=row.prospective_eligible,
        prospective_sufficient=row.prospective_sufficient,
        prospective_below=row.prospective_below,
        prospective_target=row.prospective_target,
        window_days_remaining=row.window_days_remaining,
        status=row.status,
        current_belief_state=row.current_belief_state,
        last_evaluated_at=row.last_evaluated_at.isoformat() if row.last_evaluated_at else None,
        updated_at=row.updated_at.isoformat(),
    )
    meta = build_meta(
        request_id=request_id,
        engine_version=settings.engine_version,
        domain_pack="life",
    )
    return success_envelope(data.model_dump(), meta)


@router.post(
    "/experiments/{experiment_id}/evaluate",
    response_model=ApiResponseEnvelope,
    status_code=status.HTTP_201_CREATED,
)
def evaluate_experiment(
    experiment_id: str,
    body: EvaluateExperimentRequest,
    response: Response,
    auth: AuthDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=256)],
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    use_case: Annotated[EvaluateExperimentUseCase, Depends(get_evaluate_experiment_use_case)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> ApiResponseEnvelope:
    require_scope(auth, PermissionScope.MANAGE_EXPERIMENT)
    command = EvaluateExperimentCommand(
        experiment_id=experiment_id,
        phase=body.phase,
        idempotency_key=idempotency_key,
        request_id=request_id,
    )
    result = use_case.execute(command, auth)
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    data = EvaluateExperimentData(**result.model_dump())
    meta = build_meta(
        request_id=request_id,
        engine_version=settings.engine_version,
        domain_pack="life",
        audit_id=result.audit_id,
    )
    return success_envelope(data.model_dump(), meta)
