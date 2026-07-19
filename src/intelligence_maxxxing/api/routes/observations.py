"""POST /api/v1/observations: the Stage 0 audited write path."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status

from intelligence_maxxxing.api.dependencies import (
    get_app_settings,
    get_request_id,
    get_submit_observation_use_case,
)
from intelligence_maxxxing.api.envelope import build_meta, success_envelope
from intelligence_maxxxing.application.use_cases import (
    SubmitObservationCommand,
    SubmitObservationUseCase,
)
from intelligence_maxxxing.config import EngineSettings
from intelligence_maxxxing.contracts.api.envelope import ApiResponseEnvelope
from intelligence_maxxxing.contracts.api.observations import (
    ObservationAcceptedData,
    SubmitObservationRequest,
)
from intelligence_maxxxing.domain.audit.models import Actor
from intelligence_maxxxing.domain.common.epistemic import ActorType
from intelligence_maxxxing.observability import get_logger
from intelligence_maxxxing.observability.logging import hash_idempotency_key

router = APIRouter()
logger = get_logger("intelligence_maxxxing.api.observations")


@router.post(
    "/observations",
    response_model=ApiResponseEnvelope,
    status_code=status.HTTP_201_CREATED,
)
def submit_observation(
    body: SubmitObservationRequest,
    response: Response,
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=256,
            description="Mandatory idempotency key for safe retries",
        ),
    ],
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    use_case: Annotated[SubmitObservationUseCase, Depends(get_submit_observation_use_case)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> ApiResponseEnvelope:
    command = SubmitObservationCommand(
        **body.model_dump(),
        idempotency_key=idempotency_key,
        request_id=request_id,
        actor=Actor(actor_type=ActorType.APPLICATION, actor_id=body.observed_by),
    )
    result = use_case.execute(command)

    if result.replayed:
        response.status_code = status.HTTP_200_OK

    logger.info(
        "observation accepted",
        extra={
            "request_id": request_id,
            "audit_id": result.audit_id,
            "event_id": result.event_id,
            "aggregate_id": result.observation_id,
            "idempotency_key_hash": hash_idempotency_key(idempotency_key),
            "replayed": result.replayed,
        },
    )

    data = ObservationAcceptedData(
        observation_id=result.observation_id,
        event_id=result.event_id,
        audit_id=result.audit_id,
        replayed=result.replayed,
    )
    meta = build_meta(
        request_id=request_id,
        engine_version=settings.engine_version,
        domain_pack=body.domain_pack,
        audit_id=result.audit_id,
    )
    return success_envelope(data.model_dump(), meta)
