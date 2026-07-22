"""Application/LLM boundary protections and API versioning.

APPLICATION_CANNOT_MUTATE_BELIEF / LLM_CANNOT_WRITE_BELIEF /
PUBLIC_API_IS_VERSIONED
"""

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import ValidationError

from intelligence_maxxxing.domain.beliefs import Belief
from intelligence_maxxxing.domain.common.base import Context, utc_now
from intelligence_maxxxing.domain.common.confidence import ConfidenceComponents

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _belief() -> Belief:
    return Belief(
        id="blf_" + "0" * 32,
        schema_version="1.0",
        subject="sleep",
        statement="early sleep helps",
        context=Context(scope="personal"),
        created_at=utc_now(),
        audit_id="aud_" + "0" * 32,
        confidence=ConfidenceComponents(explanation="placeholder contract"),
        supporting_evidence_ids=("evd_" + "0" * 32,),
        revalidation_policy="review monthly",
    )


def _api_routes(app: FastAPI) -> list[APIRoute]:
    return [route for route in app.routes if isinstance(route, APIRoute)]


def test_application_cannot_mutate_belief(app: FastAPI) -> None:
    """No public endpoint writes beliefs, and Belief objects are immutable."""
    belief = _belief()
    with pytest.raises(ValidationError):
        belief.statement = "rewritten by an application"  # type: ignore[misc]

    offenders = [
        f"{route.methods} {route.path}"
        for route in _api_routes(app)
        if "belief" in route.path.lower() and (route.methods or set()) & WRITE_METHODS
    ]
    assert not offenders, f"applications must never write beliefs: {offenders}"


def test_llm_cannot_write_belief(app: FastAPI) -> None:
    """There is no direct belief-write surface: not for apps, not for LLMs.

    Stage 3 allows governed hypothesis/experiment evaluation (which produces
    belief snapshots internally), but no POST/PUT/PATCH/DELETE route may write
    beliefs directly. Belief objects remain frozen; only GET routes expose them.
    """
    write_routes = sorted(
        route.path for route in _api_routes(app) if (route.methods or set()) & WRITE_METHODS
    )
    allowed_writes = {
        "/api/v1/observations",
        "/api/v1/hypotheses",
        "/api/v1/hypotheses/{hypothesis_id}/activate",
        "/api/v1/hypotheses/{hypothesis_id}/retire",
        "/api/v1/experiments/{experiment_id}/evaluate",
        # Human wellbeing feedback (ANALYZE/EXPLAIN calibration) — not belief writes.
        "/api/v1/wellbeing/feedback",
        # TMX read-only trading assessment ingest — not belief writes; no TMX imports.
        "/api/v1/trading/assessments",
        # M2 agent artifacts — parallel non-authoritative research; no belief writes.
        "/api/v1/trading/context-assessments",
        "/api/v1/trading/anomaly-findings",
        "/api/v1/trading/critic-reviews",
        "/api/v1/trading/shadow-adjudications",
        "/api/v1/trading/agent-bundle/runs",
        # M3A Research Factory Foundation — append-only research registries; no belief writes.
        "/api/v1/research/hypotheses",
        "/api/v1/research/evidence",
        "/api/v1/research/experiments",
        "/api/v1/research/experiments/{experiment_id}/manual-approve",
        "/api/v1/research/seed",
        # M3B Evidence/Safety/Report foundation — append-only research artifacts; no belief writes.
        "/api/v1/research/evidence-bundles",
        "/api/v1/research/safety-audits",
        "/api/v1/research/reports",
    }
    assert set(write_routes) == allowed_writes, (
        f"unexpected public write paths; allowed={allowed_writes}, found={write_routes}"
    )

    belief_write_routes = [
        f"{route.methods} {route.path}"
        for route in _api_routes(app)
        if "belief" in route.path.lower() and (route.methods or set()) & WRITE_METHODS
    ]
    assert not belief_write_routes, f"beliefs must never be written via HTTP: {belief_write_routes}"

    belief = _belief()
    with pytest.raises(ValidationError):
        belief.confidence = ConfidenceComponents(explanation="llm override")  # type: ignore[misc]


def test_public_api_is_versioned(app: FastAPI) -> None:
    # Public liveness/readiness probes are intentionally unversioned and
    # unauthenticated (Stage 1 §14). Everything else must live under /api/v1.
    allowed_unversioned = {"/health/live", "/health/ready", "/openapi.json", "/docs", "/redoc"}
    unversioned = [
        route.path
        for route in _api_routes(app)
        if not route.path.startswith("/api/v1/") and route.path not in allowed_unversioned
    ]
    assert not unversioned, f"all public API endpoints must live under /api/v1: {unversioned}"
