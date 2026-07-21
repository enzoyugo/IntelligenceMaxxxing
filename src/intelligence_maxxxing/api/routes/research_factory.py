"""M3A Research Factory API — /api/v1/research/* (separate from Stage 3 epistemic routes)."""

from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse

from intelligence_maxxxing.api.envelope import build_meta, success_envelope
from intelligence_maxxxing.application.errors import ApplicationError
from intelligence_maxxxing.application.use_cases.research_factory_m3a import (
    ResearchFactoryNotFoundError,
    ResearchFactoryService,
)
from intelligence_maxxxing.config import EngineSettings, get_settings
from intelligence_maxxxing.contracts.api.envelope import ApiResponseEnvelope

router = APIRouter(prefix="/research", tags=["research-factory-m3a"])

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


def get_rf_service() -> ResearchFactoryService:
    return ResearchFactoryService()


@router.get("/health", response_model=ApiResponseEnvelope)
def research_health(
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchFactoryService, Depends(get_rf_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    _ = x_trading_bridge_token
    request_id = getattr(request.state, "request_id", "req_rf_health")
    return success_envelope(
        service.health(),
        build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3a"),
    )


@router.get("/hypotheses", response_model=ApiResponseEnvelope)
def list_hypotheses(
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchFactoryService, Depends(get_rf_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
    limit: int = 100,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_rf_hyp_list")
    return success_envelope(
        service.list_hypotheses(limit=max(1, min(limit, 500))),
        build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3a"),
    )


@router.post("/hypotheses", response_model=ApiResponseEnvelope, status_code=status.HTTP_201_CREATED)
def create_hypothesis(
    body: dict[str, Any],
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchFactoryService, Depends(get_rf_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_rf_hyp_create")
    try:
        data = service.create_hypothesis(body, actor=str(body.get("created_by") or "human"))
    except ApplicationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"ok": False, "error": {"code": getattr(exc, "code", "ERROR"), "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3a")
    )


@router.get("/hypotheses/{hypothesis_id}", response_model=ApiResponseEnvelope)
def get_hypothesis(
    hypothesis_id: str,
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchFactoryService, Depends(get_rf_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_rf_hyp_get")
    try:
        data = service.get_hypothesis(hypothesis_id)
    except ResearchFactoryNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"ok": False, "error": {"code": exc.code, "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3a")
    )


@router.get("/evidence", response_model=ApiResponseEnvelope)
def list_evidence(
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchFactoryService, Depends(get_rf_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
    limit: int = 200,
    hypothesis_id: str | None = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_rf_evd_list")
    return success_envelope(
        service.list_evidence(limit=max(1, min(limit, 500)), hypothesis_id=hypothesis_id),
        build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3a"),
    )


@router.post("/evidence", response_model=ApiResponseEnvelope, status_code=status.HTTP_201_CREATED)
def create_evidence(
    body: dict[str, Any],
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchFactoryService, Depends(get_rf_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_rf_evd_create")
    try:
        data = service.create_evidence(body)
    except ApplicationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"ok": False, "error": {"code": getattr(exc, "code", "ERROR"), "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3a")
    )


@router.get("/evidence/{evidence_id}", response_model=ApiResponseEnvelope)
def get_evidence(
    evidence_id: str,
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchFactoryService, Depends(get_rf_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_rf_evd_get")
    try:
        data = service.get_evidence(evidence_id)
    except ResearchFactoryNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"ok": False, "error": {"code": exc.code, "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3a")
    )


@router.get("/experiments", response_model=ApiResponseEnvelope)
def list_experiments(
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchFactoryService, Depends(get_rf_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
    limit: int = 100,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_rf_exp_list")
    return success_envelope(
        service.list_experiments(limit=max(1, min(limit, 500))),
        build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3a"),
    )


@router.post("/experiments", response_model=ApiResponseEnvelope, status_code=status.HTTP_201_CREATED)
def create_experiment(
    body: dict[str, Any],
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchFactoryService, Depends(get_rf_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_rf_exp_create")
    try:
        data = service.create_experiment(body)
    except ApplicationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"ok": False, "error": {"code": getattr(exc, "code", "ERROR"), "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3a")
    )


@router.get("/experiments/{experiment_id}", response_model=ApiResponseEnvelope)
def get_experiment(
    experiment_id: str,
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchFactoryService, Depends(get_rf_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_rf_exp_get")
    try:
        data = service.get_experiment(experiment_id)
    except ResearchFactoryNotFoundError as exc:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"ok": False, "error": {"code": exc.code, "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3a")
    )


@router.post(
    "/experiments/{experiment_id}/manual-approve",
    response_model=ApiResponseEnvelope,
)
def manual_approve(
    experiment_id: str,
    body: dict[str, Any],
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchFactoryService, Depends(get_rf_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_rf_exp_approve")
    try:
        data = service.manually_approve_experiment(
            experiment_id,
            actor=str(body.get("actor") or ""),
            confirmation=str(body.get("confirmation") or ""),
        )
    except ApplicationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"ok": False, "error": {"code": getattr(exc, "code", "ERROR"), "message": exc.message}},
        )
    return success_envelope(
        data, build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3a")
    )


@router.get("/learning-memory", response_model=ApiResponseEnvelope)
def learning_memory(
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchFactoryService, Depends(get_rf_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
    limit: int = 100,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_rf_learn")
    return success_envelope(
        service.list_learning(limit=max(1, min(limit, 500))),
        build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3a"),
    )


@router.get("/priorities", response_model=ApiResponseEnvelope)
def priorities(
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchFactoryService, Depends(get_rf_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_rf_prio")
    return success_envelope(
        service.priorities(),
        build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3a"),
    )


@router.post("/seed", response_model=ApiResponseEnvelope, status_code=status.HTTP_201_CREATED)
def seed(
    request: Request,
    settings: Annotated[EngineSettings, Depends(get_settings)],
    service: Annotated[ResearchFactoryService, Depends(get_rf_service)],
    x_trading_bridge_token: Annotated[str | None, Header()] = None,
) -> Any:
    denied = _auth_or_dev(x_trading_bridge_token, settings)
    if denied is not None:
        return denied
    request_id = getattr(request.state, "request_id", "req_rf_seed")
    return success_envelope(
        service.seed_canonical_evidence(),
        build_meta(request_id, settings.engine_version, domain_pack="research_factory_m3a"),
    )
