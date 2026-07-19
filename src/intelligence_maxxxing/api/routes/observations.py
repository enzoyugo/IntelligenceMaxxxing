"""Observation write and read endpoints (Stage 1: authenticated, scoped)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status

from intelligence_maxxxing.api.dependencies import (
    AuthDep,
    get_app_settings,
    get_list_observations_use_case,
    get_observation_use_case,
    get_request_id,
    get_submit_observation_use_case,
)
from intelligence_maxxxing.api.envelope import build_meta, success_envelope
from intelligence_maxxxing.application.auth import require_scope
from intelligence_maxxxing.application.ports import ObservationListFilters
from intelligence_maxxxing.application.use_cases import (
    SubmitObservationCommand,
    SubmitObservationUseCase,
)
from intelligence_maxxxing.application.use_cases.read_observations import (
    GetObservationUseCase,
    ListObservationsUseCase,
)
from intelligence_maxxxing.config import EngineSettings
from intelligence_maxxxing.contracts.api.envelope import ApiResponseEnvelope
from intelligence_maxxxing.contracts.api.observations import (
    ObservationAcceptedData,
    ObservationListData,
    ObservationView,
    SubmitObservationRequest,
)
from intelligence_maxxxing.observability import get_logger
from intelligence_maxxxing.observability.logging import hash_idempotency_key
from intelligence_maxxxing.permissions import PermissionScope

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
    auth: AuthDep,
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
    require_scope(auth, PermissionScope.SUBMIT_OBSERVATION)
    # Actor identity comes exclusively from auth; the body cannot spoof it.
    command = SubmitObservationCommand(
        **body.model_dump(),
        idempotency_key=idempotency_key,
        request_id=request_id,
    )
    result = use_case.execute(command, auth)

    if result.replayed:
        response.status_code = status.HTTP_200_OK

    logger.info(
        "observation accepted",
        extra={
            "request_id": request_id,
            "audit_id": result.audit_id,
            "event_id": result.event_id,
            "aggregate_id": result.observation_id,
            "application_id": auth.application_id,
            "owner_id": auth.owner_id,
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


@router.get("/observations/{observation_id}", response_model=ApiResponseEnvelope)
def get_observation(
    observation_id: str,
    auth: AuthDep,
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    use_case: Annotated[GetObservationUseCase, Depends(get_observation_use_case)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> ApiResponseEnvelope:
    require_scope(auth, PermissionScope.READ_INTELLIGENCE)
    row = use_case.execute(observation_id, auth)
    data = ObservationView(
        observation_id=row.observation_id,
        schema_version=row.schema_version,
        domain_pack=row.domain_pack,
        subject=row.subject,
        statement=row.statement,
        knowledge_class=row.knowledge_class,
        unknown_reason=row.unknown_reason,
        observed_by=row.observed_by,
        context=row.context,
        source_ids=row.source_ids,
        metadata=row.metadata,
        occurred_at=row.occurred_at.isoformat() if row.occurred_at else None,
        created_at=row.created_at.isoformat(),
        audit_id=row.audit_id,
        event_id=row.event_id,
        global_position=row.global_position,
    )
    meta = build_meta(
        request_id=request_id,
        engine_version=settings.engine_version,
        domain_pack=row.domain_pack,
        audit_id=row.audit_id,
    )
    return success_envelope(data.model_dump(), meta)


@router.get("/observations", response_model=ApiResponseEnvelope)
def list_observations(
    auth: AuthDep,
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    use_case: Annotated[ListObservationsUseCase, Depends(get_list_observations_use_case)],
    request_id: Annotated[str, Depends(get_request_id)],
    domain_pack: Annotated[str | None, Query()] = None,
    occurred_from: Annotated[datetime | None, Query()] = None,
    occurred_to: Annotated[datetime | None, Query()] = None,
    cursor: Annotated[int | None, Query(description="global_position cursor")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> ApiResponseEnvelope:
    require_scope(auth, PermissionScope.READ_INTELLIGENCE)
    page = use_case.execute(
        ObservationListFilters(
            domain_pack=domain_pack,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            after_position=cursor,
            limit=limit,
        ),
        auth,
    )
    data = ObservationListData(
        items=tuple(
            ObservationView(
                observation_id=row.observation_id,
                schema_version=row.schema_version,
                domain_pack=row.domain_pack,
                subject=row.subject,
                statement=row.statement,
                knowledge_class=row.knowledge_class,
                unknown_reason=row.unknown_reason,
                observed_by=row.observed_by,
                context=row.context,
                source_ids=row.source_ids,
                metadata=row.metadata,
                occurred_at=row.occurred_at.isoformat() if row.occurred_at else None,
                created_at=row.created_at.isoformat(),
                audit_id=row.audit_id,
                event_id=row.event_id,
                global_position=row.global_position,
            )
            for row in page.items
        ),
        next_cursor=page.next_cursor,
        projection_name=page.projection_name,
        projection_version=page.projection_version,
        projection_position=page.projection_position,
        projection_updated_at=page.projection_updated_at,
    )
    meta = build_meta(
        request_id=request_id,
        engine_version=settings.engine_version,
        freshness={
            "projection_name": page.projection_name,
            "projection_version": page.projection_version,
            "projection_position": (
                str(page.projection_position) if page.projection_position is not None else ""
            ),
        },
    )
    return success_envelope(data.model_dump(), meta)
