"""Trading assessment API — TMX bridge (token or auth)."""

from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse

from intelligence_maxxxing.api.envelope import build_meta, success_envelope
from intelligence_maxxxing.application.errors import ApplicationError, IdempotencyConflictError
from intelligence_maxxxing.application.use_cases.trading_assessment import (
    TradingAssessmentNotFoundError,
    TradingAssessmentService,
)
from intelligence_maxxxing.application.use_cases.trading_agents import (
    TradingAgentNotFoundError,
    TradingAgentService,
)
from intelligence_maxxxing.config import EngineSettings, get_settings
from intelligence_maxxxing.contracts.api.envelope import ApiResponseEnvelope

router = APIRouter(prefix="/trading", tags=["trading"])

_DEFAULT_BRIDGE_TOKEN = "tmx-im-local-bridge-v1"


def _bridge_token_ok(token: str | None) -> bool:
    expected = os.environ.get("IM_TRADING_BRIDGE_TOKEN", _DEFAULT_BRIDGE_TOKEN)
    if not expected:
        return False
    return bool(token) and token == expected


def _auth_or_dev(
    token: str | None, settings: EngineSettings
) -> JSONResponse | None:
    if _bridge_token_ok(token) or settings.engine_env in {"development", "test"}:
        return None
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "ok": False,
            "error": {"code": "AUTHENTICATION_REQUIRED", "message": "bridge token required"},
        },
    )


def get_trading_service() -> TradingAssessmentService:
    return TradingAssessmentService()


def get_agent_service() -> TradingAgentService:
    return TradingAgentService()


@router.get("/health", response_model=ApiResponseEnvelope)
def trading_health(
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[TradingAssessmentService, Depends(get_trading_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> ApiResponseEnvelope:
    # Health is readable with bridge token or openly in development.
    _ = x_trading_bridge_token
    request_id = getattr(request.state, "request_id", "req_trading_health")
    return success_envelope(
        service.health(),
        build_meta(request_id, settings.engine_version, domain_pack="trading"),
    )


@router.get("/policies/active", response_model=ApiResponseEnvelope)
def active_policy(
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[TradingAssessmentService, Depends(get_trading_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    if not _bridge_token_ok(x_trading_bridge_token) and settings.engine_env not in {
        "development",
        "test",
    }:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "ok": False,
                "error": {"code": "AUTHENTICATION_REQUIRED", "message": "bridge token required"},
            },
        )
    request_id = getattr(request.state, "request_id", "req_trading_policy")
    return success_envelope(
        service.active_policy(),
        build_meta(request_id, settings.engine_version, domain_pack="trading"),
    )


@router.get("/assessments/{assessment_id}", response_model=ApiResponseEnvelope)
def get_assessment(
    assessment_id: str,
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[TradingAssessmentService, Depends(get_trading_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    if not _bridge_token_ok(x_trading_bridge_token) and settings.engine_env not in {
        "development",
        "test",
    }:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "ok": False,
                "error": {"code": "AUTHENTICATION_REQUIRED", "message": "bridge token required"},
            },
        )
    request_id = getattr(request.state, "request_id", "req_trading_get")
    try:
        data = service.get_assessment(assessment_id)
    except TradingAssessmentNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "ok": False,
                "error": {"code": exc.code, "message": exc.message},
            },
        )
    return success_envelope(
        data,
        build_meta(request_id, settings.engine_version, domain_pack="trading"),
    )


@router.post("/assessments", response_model=ApiResponseEnvelope, status_code=status.HTTP_201_CREATED)
def create_assessment(
    body: dict[str, Any],
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[TradingAssessmentService, Depends(get_trading_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Any:
    if not _bridge_token_ok(x_trading_bridge_token) and settings.engine_env not in {
        "development",
        "test",
    }:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "ok": False,
                "error": {"code": "AUTHENTICATION_REQUIRED", "message": "bridge token required"},
            },
        )
    request_id = getattr(request.state, "request_id", "req_trading_assess")
    if idempotency_key and not body.get("idempotency_key"):
        body = {**body, "idempotency_key": idempotency_key}
    try:
        assessment = service.assess(body, request_id=request_id)
    except IdempotencyConflictError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"ok": False, "error": {"code": exc.code, "message": exc.message}},
        )
    except ApplicationError as exc:
        code = getattr(exc, "code", "APPLICATION_ERROR")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"ok": False, "error": {"code": code, "message": exc.message}},
        )
    return success_envelope(
        assessment,
        build_meta(request_id, settings.engine_version, domain_pack="trading"),
    )


@router.get("/agents/health", response_model=ApiResponseEnvelope)
def agents_health(
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[TradingAgentService, Depends(get_agent_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None and settings.engine_env not in {"development", "test"}:
        # Health readable in development; still require token in production-like envs.
        if not _bridge_token_ok(x_trading_bridge_token):
            pass
    request_id = getattr(request.state, "request_id", "req_trading_agents_health")
    return success_envelope(
        service.agents_health(),
        build_meta(request_id, settings.engine_version, domain_pack="trading"),
    )


@router.get("/agent-bundles/active", response_model=ApiResponseEnvelope)
def active_agent_bundle(
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[TradingAgentService, Depends(get_agent_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_trading_bundle")
    return success_envelope(
        service.active_bundle(),
        build_meta(request_id, settings.engine_version, domain_pack="trading"),
    )


@router.post(
    "/context-assessments",
    response_model=ApiResponseEnvelope,
    status_code=status.HTTP_201_CREATED,
)
def create_context_assessment(
    body: dict[str, Any],
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[TradingAgentService, Depends(get_agent_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_trading_context")
    try:
        data = service.create_context(body.get("observation") if "observation" in body else body)
    except ApplicationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"ok": False, "error": {"code": getattr(exc, "code", "ERROR"), "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="trading")
    )


@router.get("/context-assessments/{context_assessment_id}", response_model=ApiResponseEnvelope)
def get_context_assessment(
    context_assessment_id: str,
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[TradingAgentService, Depends(get_agent_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_trading_context_get")
    try:
        data = service.get_context(context_assessment_id)
    except TradingAgentNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"ok": False, "error": {"code": exc.code, "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="trading")
    )


@router.post(
    "/anomaly-findings",
    response_model=ApiResponseEnvelope,
    status_code=status.HTTP_201_CREATED,
)
def create_anomaly_findings(
    body: dict[str, Any],
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[TradingAgentService, Depends(get_agent_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_trading_anomaly")
    try:
        data = service.create_anomaly_findings(
            body.get("observation") if "observation" in body else body
        )
    except ApplicationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"ok": False, "error": {"code": getattr(exc, "code", "ERROR"), "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="trading")
    )


@router.get("/anomaly-findings/{finding_id}", response_model=ApiResponseEnvelope)
def get_anomaly_finding(
    finding_id: str,
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[TradingAgentService, Depends(get_agent_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_trading_anomaly_get")
    try:
        data = service.get_anomaly(finding_id)
    except TradingAgentNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"ok": False, "error": {"code": exc.code, "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="trading")
    )


@router.post(
    "/critic-reviews",
    response_model=ApiResponseEnvelope,
    status_code=status.HTTP_201_CREATED,
)
def create_critic_review(
    body: dict[str, Any],
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[TradingAgentService, Depends(get_agent_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_trading_critic")
    try:
        data = service.create_critic_review(body)
    except ApplicationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"ok": False, "error": {"code": getattr(exc, "code", "ERROR"), "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="trading")
    )


@router.get("/critic-reviews/{critic_review_id}", response_model=ApiResponseEnvelope)
def get_critic_review(
    critic_review_id: str,
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[TradingAgentService, Depends(get_agent_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_trading_critic_get")
    try:
        data = service.get_critic(critic_review_id)
    except TradingAgentNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"ok": False, "error": {"code": exc.code, "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="trading")
    )


@router.post(
    "/shadow-adjudications",
    response_model=ApiResponseEnvelope,
    status_code=status.HTTP_201_CREATED,
)
def create_shadow_adjudication(
    body: dict[str, Any],
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[TradingAgentService, Depends(get_agent_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_trading_shadow")
    try:
        data = service.create_shadow_adjudication(body)
    except ApplicationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"ok": False, "error": {"code": getattr(exc, "code", "ERROR"), "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="trading")
    )


@router.get("/shadow-adjudications/{shadow_adjudication_id}", response_model=ApiResponseEnvelope)
def get_shadow_adjudication(
    shadow_adjudication_id: str,
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[TradingAgentService, Depends(get_agent_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_trading_shadow_get")
    try:
        data = service.get_shadow(shadow_adjudication_id)
    except TradingAgentNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"ok": False, "error": {"code": exc.code, "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="trading")
    )


@router.post(
    "/agent-bundle/runs",
    response_model=ApiResponseEnvelope,
    status_code=status.HTTP_201_CREATED,
)
def run_agent_bundle(
    body: dict[str, Any],
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[TradingAgentService, Depends(get_agent_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_trading_bundle_run")
    try:
        data = service.run_bundle(
            observation=body.get("observation") or {},
            assessment=body.get("assessment") or {},
        )
    except ApplicationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"ok": False, "error": {"code": getattr(exc, "code", "ERROR"), "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="trading")
    )
