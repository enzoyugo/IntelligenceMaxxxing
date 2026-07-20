"""Hypothesis endpoints (Stage 3: propose, activate, retire, read)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Response, status

from intelligence_maxxxing.api.dependencies import (
    AuthDep,
    get_activate_hypothesis_use_case,
    get_app_settings,
    get_current_belief_use_case,
    get_hypothesis_use_case,
    get_list_beliefs_use_case,
    get_list_hypotheses_use_case,
    get_list_learning_use_case,
    get_propose_hypothesis_use_case,
    get_request_id,
    get_retire_hypothesis_use_case,
)
from intelligence_maxxxing.api.envelope import build_meta, success_envelope
from intelligence_maxxxing.application.auth import require_scope
from intelligence_maxxxing.application.ports import ProjectedHypothesis
from intelligence_maxxxing.application.use_cases.epistemic import (
    ActivateHypothesisCommand,
    ActivateHypothesisUseCase,
    GetCurrentBeliefUseCase,
    GetHypothesisUseCase,
    ListBeliefsUseCase,
    ListHypothesesUseCase,
    ListLearningUseCase,
    ProposeHypothesisCommand,
    ProposeHypothesisUseCase,
    RetireHypothesisCommand,
    RetireHypothesisUseCase,
)
from intelligence_maxxxing.config import EngineSettings
from intelligence_maxxxing.contracts.api.envelope import ApiResponseEnvelope
from intelligence_maxxxing.contracts.api.hypotheses import (
    ActivateHypothesisData,
    ActivateHypothesisRequest,
    BeliefListData,
    BeliefView,
    HypothesisListData,
    HypothesisView,
    LearningListData,
    LearningView,
    ProposeHypothesisData,
    ProposeHypothesisRequest,
    RetireHypothesisData,
    RetireHypothesisRequest,
)
from intelligence_maxxxing.permissions import PermissionScope

router = APIRouter()


def _hypothesis_view(row: ProjectedHypothesis) -> HypothesisView:
    return HypothesisView(
        hypothesis_id=row.hypothesis_id,
        template_id=row.template_id,
        template_version=row.template_version,
        statement=row.statement,
        direction=row.direction,
        causality_level=row.causality_level,
        status=row.status,
        human_confirmed=row.human_confirmed,
        parameters=row.parameters,
        proposed_at=row.proposed_at.isoformat(),
        activated_at=row.activated_at.isoformat() if row.activated_at else None,
        retired_at=row.retired_at.isoformat() if row.retired_at else None,
        experiment_id=row.experiment_id,
        audit_id=row.audit_id,
        event_id=row.event_id,
    )


@router.post("/hypotheses", response_model=ApiResponseEnvelope, status_code=status.HTTP_201_CREATED)
def propose_hypothesis(
    body: ProposeHypothesisRequest,
    response: Response,
    auth: AuthDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=256)],
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    use_case: Annotated[ProposeHypothesisUseCase, Depends(get_propose_hypothesis_use_case)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> ApiResponseEnvelope:
    require_scope(auth, PermissionScope.SUBMIT_HYPOTHESIS)
    command = ProposeHypothesisCommand(
        **body.model_dump(),
        idempotency_key=idempotency_key,
        request_id=request_id,
    )
    result = use_case.execute(command, auth)
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    data = ProposeHypothesisData(**result.model_dump())
    meta = build_meta(
        request_id=request_id,
        engine_version=settings.engine_version,
        domain_pack="life",
        audit_id=result.audit_id,
    )
    return success_envelope(data.model_dump(), meta)


@router.post(
    "/hypotheses/{hypothesis_id}/activate",
    response_model=ApiResponseEnvelope,
    status_code=status.HTTP_201_CREATED,
)
def activate_hypothesis(
    hypothesis_id: str,
    body: ActivateHypothesisRequest,
    response: Response,
    auth: AuthDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=256)],
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    use_case: Annotated[ActivateHypothesisUseCase, Depends(get_activate_hypothesis_use_case)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> ApiResponseEnvelope:
    require_scope(auth, PermissionScope.MANAGE_EXPERIMENT)
    command = ActivateHypothesisCommand(
        hypothesis_id=hypothesis_id,
        parameters=body.parameters,
        idempotency_key=idempotency_key,
        request_id=request_id,
    )
    result = use_case.execute(command, auth)
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    data = ActivateHypothesisData(**result.model_dump())
    meta = build_meta(
        request_id=request_id,
        engine_version=settings.engine_version,
        domain_pack="life",
        audit_id=result.audit_id,
    )
    return success_envelope(data.model_dump(), meta)


@router.post(
    "/hypotheses/{hypothesis_id}/retire",
    response_model=ApiResponseEnvelope,
    status_code=status.HTTP_201_CREATED,
)
def retire_hypothesis(
    hypothesis_id: str,
    body: RetireHypothesisRequest,
    response: Response,
    auth: AuthDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=256)],
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    use_case: Annotated[RetireHypothesisUseCase, Depends(get_retire_hypothesis_use_case)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> ApiResponseEnvelope:
    require_scope(auth, PermissionScope.MANAGE_EXPERIMENT)
    command = RetireHypothesisCommand(
        hypothesis_id=hypothesis_id,
        reason=body.reason,
        idempotency_key=idempotency_key,
        request_id=request_id,
    )
    result = use_case.execute(command, auth)
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    data = RetireHypothesisData(**result.model_dump())
    meta = build_meta(
        request_id=request_id,
        engine_version=settings.engine_version,
        domain_pack="life",
        audit_id=result.audit_id,
    )
    return success_envelope(data.model_dump(), meta)


@router.get("/hypotheses/{hypothesis_id}", response_model=ApiResponseEnvelope)
def get_hypothesis(
    hypothesis_id: str,
    auth: AuthDep,
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    use_case: Annotated[GetHypothesisUseCase, Depends(get_hypothesis_use_case)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> ApiResponseEnvelope:
    require_scope(auth, PermissionScope.READ_HYPOTHESIS)
    row = use_case.execute(hypothesis_id, auth)
    data = _hypothesis_view(row)
    meta = build_meta(
        request_id=request_id,
        engine_version=settings.engine_version,
        domain_pack="life",
        audit_id=row.audit_id,
    )
    return success_envelope(data.model_dump(), meta)


@router.get("/hypotheses", response_model=ApiResponseEnvelope)
def list_hypotheses(
    auth: AuthDep,
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    use_case: Annotated[ListHypothesesUseCase, Depends(get_list_hypotheses_use_case)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> ApiResponseEnvelope:
    require_scope(auth, PermissionScope.READ_HYPOTHESIS)
    rows = use_case.execute(auth)
    data = HypothesisListData(items=tuple(_hypothesis_view(r) for r in rows))
    meta = build_meta(
        request_id=request_id,
        engine_version=settings.engine_version,
        domain_pack="life",
    )
    return success_envelope(data.model_dump(), meta)


@router.get("/hypotheses/{hypothesis_id}/beliefs/current", response_model=ApiResponseEnvelope)
def get_current_belief(
    hypothesis_id: str,
    auth: AuthDep,
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    use_case: Annotated[GetCurrentBeliefUseCase, Depends(get_current_belief_use_case)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> ApiResponseEnvelope:
    require_scope(auth, PermissionScope.READ_BELIEF)
    row = use_case.execute(hypothesis_id, auth)
    if row is None:
        meta = build_meta(
            request_id=request_id,
            engine_version=settings.engine_version,
            domain_pack="life",
        )
        empty: dict[str, Any] | None = None
        return success_envelope(empty, meta)
    view = BeliefView(
        belief_id=row.belief_id,
        hypothesis_id=row.hypothesis_id,
        evidence_id=row.evidence_id,
        previous_belief_id=row.previous_belief_id,
        belief_state=row.belief_state,
        model_probability=row.model_probability,
        credible_interval_low=row.credible_interval_low,
        credible_interval_high=row.credible_interval_high,
        estimated_effect=row.estimated_effect,
        minimum_meaningful_difference=row.minimum_meaningful_difference,
        data_confidence=row.data_confidence,
        method_confidence=row.method_confidence,
        conclusion_confidence=row.conclusion_confidence,
        recommendation_confidence=row.recommendation_confidence,
        calibration_state=row.calibration_state,
        causality_level=row.causality_level,
        limitations=row.limitations,
        is_current=row.is_current,
        created_at=row.created_at.isoformat(),
        audit_id=row.audit_id,
        event_id=row.event_id,
    )
    meta = build_meta(
        request_id=request_id,
        engine_version=settings.engine_version,
        domain_pack="life",
        audit_id=row.audit_id,
    )
    return success_envelope(view.model_dump(), meta)


@router.get("/hypotheses/{hypothesis_id}/beliefs", response_model=ApiResponseEnvelope)
def list_beliefs(
    hypothesis_id: str,
    auth: AuthDep,
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    use_case: Annotated[ListBeliefsUseCase, Depends(get_list_beliefs_use_case)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> ApiResponseEnvelope:
    require_scope(auth, PermissionScope.READ_BELIEF)
    rows = use_case.execute(hypothesis_id, auth)
    items = tuple(
        BeliefView(
            belief_id=row.belief_id,
            hypothesis_id=row.hypothesis_id,
            evidence_id=row.evidence_id,
            previous_belief_id=row.previous_belief_id,
            belief_state=row.belief_state,
            model_probability=row.model_probability,
            credible_interval_low=row.credible_interval_low,
            credible_interval_high=row.credible_interval_high,
            estimated_effect=row.estimated_effect,
            minimum_meaningful_difference=row.minimum_meaningful_difference,
            data_confidence=row.data_confidence,
            method_confidence=row.method_confidence,
            conclusion_confidence=row.conclusion_confidence,
            recommendation_confidence=row.recommendation_confidence,
            calibration_state=row.calibration_state,
            causality_level=row.causality_level,
            limitations=row.limitations,
            is_current=row.is_current,
            created_at=row.created_at.isoformat(),
            audit_id=row.audit_id,
            event_id=row.event_id,
        )
        for row in rows
    )
    data = BeliefListData(items=items)
    meta = build_meta(
        request_id=request_id,
        engine_version=settings.engine_version,
        domain_pack="life",
    )
    return success_envelope(data.model_dump(), meta)


@router.get("/hypotheses/{hypothesis_id}/learning", response_model=ApiResponseEnvelope)
def list_learning(
    hypothesis_id: str,
    auth: AuthDep,
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    use_case: Annotated[ListLearningUseCase, Depends(get_list_learning_use_case)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> ApiResponseEnvelope:
    require_scope(auth, PermissionScope.READ_LEARNING)
    rows = use_case.execute(hypothesis_id, auth)
    items = tuple(
        LearningView(
            learning_id=row.learning_id,
            hypothesis_id=row.hypothesis_id,
            previous_belief_id=row.previous_belief_id,
            new_belief_id=row.new_belief_id,
            outcome_evaluation_id=row.outcome_evaluation_id,
            change_type=row.change_type,
            what_changed=row.what_changed,
            why_changed=row.why_changed,
            what_remains_unknown=row.what_remains_unknown,
            next_evidence_needed=row.next_evidence_needed,
            created_at=row.created_at.isoformat(),
            audit_id=row.audit_id,
            event_id=row.event_id,
        )
        for row in rows
    )
    data = LearningListData(items=items)
    meta = build_meta(
        request_id=request_id,
        engine_version=settings.engine_version,
        domain_pack="life",
    )
    return success_envelope(data.model_dump(), meta)
