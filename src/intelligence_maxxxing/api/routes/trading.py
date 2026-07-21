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
from intelligence_maxxxing.config import EngineSettings, get_settings
from intelligence_maxxxing.contracts.api.envelope import ApiResponseEnvelope

router = APIRouter(prefix="/trading", tags=["trading"])

_DEFAULT_BRIDGE_TOKEN = "tmx-im-local-bridge-v1"


def _bridge_token_ok(token: str | None) -> bool:
    expected = os.environ.get("IM_TRADING_BRIDGE_TOKEN", _DEFAULT_BRIDGE_TOKEN)
    if not expected:
        return False
    return bool(token) and token == expected


def get_trading_service() -> TradingAssessmentService:
    return TradingAssessmentService()


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
