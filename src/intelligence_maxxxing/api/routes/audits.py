"""GET /api/v1/audits/{audit_id}: recoverable audit trail."""

from typing import Annotated

from fastapi import APIRouter, Depends

from intelligence_maxxxing.api.dependencies import (
    get_app_settings,
    get_audit_use_case,
    get_request_id,
)
from intelligence_maxxxing.api.envelope import build_meta, success_envelope
from intelligence_maxxxing.application.use_cases import GetAuditUseCase
from intelligence_maxxxing.config import EngineSettings
from intelligence_maxxxing.contracts.api.audits import AuditRecordData, PublicEngineEvent
from intelligence_maxxxing.contracts.api.envelope import ApiResponseEnvelope

router = APIRouter()


@router.get("/audits/{audit_id}", response_model=ApiResponseEnvelope)
def get_audit(
    audit_id: str,
    settings: Annotated[EngineSettings, Depends(get_app_settings)],
    use_case: Annotated[GetAuditUseCase, Depends(get_audit_use_case)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> ApiResponseEnvelope:
    bundle = use_case.execute(audit_id)
    audit = bundle.audit

    data = AuditRecordData(
        audit_id=audit.audit_id,
        request_id=audit.request_id,
        engine_version=audit.engine_version,
        api_version=audit.api_version,
        schema_version=audit.schema_version,
        domain_pack=audit.domain_pack,
        actor_type=audit.actor.actor_type.value,
        actor_id=audit.actor.actor_id,
        action=audit.action,
        input_object_ids=audit.input_object_ids,
        output_object_ids=audit.output_object_ids,
        event_ids=audit.event_ids,
        timestamp=audit.timestamp.isoformat(),
        health_state=dict(audit.health_state),
        events=tuple(
            PublicEngineEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                aggregate_version=event.aggregate_version,
                domain_pack=event.domain_pack,
                schema_version=event.schema_version,
                payload=dict(event.payload),
                occurred_at=event.occurred_at.isoformat(),
                recorded_at=event.recorded_at.isoformat(),
            )
            for event in bundle.events
        ),
    )
    meta = build_meta(
        request_id=request_id,
        engine_version=settings.engine_version,
        domain_pack=audit.domain_pack,
        audit_id=audit.audit_id,
    )
    return success_envelope(data.model_dump(), meta)
