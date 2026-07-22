"""M3B Evidence / Safety / Report API — /api/v1/research/* (alongside M3A)."""

from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse

from intelligence_maxxxing.api.envelope import build_meta, success_envelope
from intelligence_maxxxing.application.errors import ApplicationError
from intelligence_maxxxing.config import EngineSettings, get_settings
from intelligence_maxxxing.contracts.api.envelope import ApiResponseEnvelope
from intelligence_maxxxing.domain_packs.research_factory_m3b.service_v1 import (
    ResearchM3BNotFoundError,
    ResearchM3BService,
)

router = APIRouter(prefix="/research", tags=["research-factory-m3b"])

_DEFAULT_BRIDGE_TOKEN = "tmx-im-local-bridge-v1"


def _token_ok(token: str | None) -> bool:
    expected = os.environ.get("IM_TRADING_BRIDGE_TOKEN", _DEFAULT_BRIDGE_TOKEN)
    return bool(token) and token == expected


def _auth_or_dev(token: str | None, settings: EngineSettings) -> JSONResponse | None:
    if _token_ok(token) or settings.engine_env in {"development", "test"}:
        return None
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"ok": False, "error": {"code": "AUTHENTICATION_REQUIRED", "message": "token required"}},
    )


def get_m3b_service() -> ResearchM3BService:
    return ResearchM3BService()


@router.get("/m3b/health", response_model=ApiResponseEnvelope)
def m3b_health(
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchM3BService, Depends(get_m3b_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    _ = x_trading_bridge_token
    request_id = getattr(request.state, "request_id", "req_m3b_health")
    return success_envelope(
        service.health(),
        build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3b"),
    )


@router.get("/evidence-bundles", response_model=ApiResponseEnvelope)
def list_evidence_bundles(
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchM3BService, Depends(get_m3b_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
    limit: int = 100,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_m3b_eb_list")
    return success_envelope(
        service.list_evidence_bundles(limit=max(1, min(limit, 500))),
        build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3b"),
    )


@router.post("/evidence-bundles", response_model=ApiResponseEnvelope, status_code=status.HTTP_201_CREATED)
def create_evidence_bundle(
    body: dict[str, Any],
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchM3BService, Depends(get_m3b_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_m3b_eb_create")
    subject = body.get("subject") if isinstance(body.get("subject"), dict) else body
    try:
        data = service.create_evidence_bundle(subject)
    except ApplicationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"ok": False, "error": {"code": getattr(exc, "code", "ERROR"), "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3b")
    )


@router.get("/evidence-bundles/{bundle_id}", response_model=ApiResponseEnvelope)
def get_evidence_bundle(
    bundle_id: str,
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchM3BService, Depends(get_m3b_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_m3b_eb_get")
    try:
        data = service.get_evidence_bundle(bundle_id)
    except ResearchM3BNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"ok": False, "error": {"code": exc.code, "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3b")
    )


@router.get("/safety-audits", response_model=ApiResponseEnvelope)
def list_safety_audits(
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchM3BService, Depends(get_m3b_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
    limit: int = 100,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_m3b_sa_list")
    return success_envelope(
        service.list_safety_audits(limit=max(1, min(limit, 500))),
        build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3b"),
    )


@router.post("/safety-audits", response_model=ApiResponseEnvelope, status_code=status.HTTP_201_CREATED)
def create_safety_audit(
    body: dict[str, Any],
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchM3BService, Depends(get_m3b_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_m3b_sa_create")
    scope = body.get("scope_payload") if isinstance(body.get("scope_payload"), dict) else body
    try:
        data = service.create_safety_audit(scope)
    except ApplicationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"ok": False, "error": {"code": getattr(exc, "code", "ERROR"), "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3b")
    )


@router.get("/safety-audits/{audit_id}", response_model=ApiResponseEnvelope)
def get_safety_audit(
    audit_id: str,
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchM3BService, Depends(get_m3b_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_m3b_sa_get")
    try:
        data = service.get_safety_audit(audit_id)
    except ResearchM3BNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"ok": False, "error": {"code": exc.code, "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3b")
    )


@router.get("/reports", response_model=ApiResponseEnvelope)
def list_reports(
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchM3BService, Depends(get_m3b_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
    limit: int = 100,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_m3b_rpt_list")
    return success_envelope(
        service.list_reports(limit=max(1, min(limit, 500))),
        build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3b"),
    )


@router.post("/reports", response_model=ApiResponseEnvelope, status_code=status.HTTP_201_CREATED)
def create_report(
    body: dict[str, Any],
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchM3BService, Depends(get_m3b_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_m3b_rpt_create")
    try:
        data = service.create_report(body)
    except ApplicationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"ok": False, "error": {"code": getattr(exc, "code", "ERROR"), "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3b")
    )


@router.get("/reports/{report_id}", response_model=ApiResponseEnvelope)
def get_report(
    report_id: str,
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchM3BService, Depends(get_m3b_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_m3b_rpt_get")
    try:
        data = service.get_report(report_id)
    except ResearchM3BNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"ok": False, "error": {"code": exc.code, "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3b")
    )
