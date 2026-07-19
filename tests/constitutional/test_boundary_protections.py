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
    """There is no belief-write surface at all: not for apps, not for LLMs.

    Stage 0 has no LLM integration. This test protects the architecture that
    will make an LLM belief-write impossible: beliefs are frozen objects, the
    only write path in the system is observation submission, and the event
    store accepts events but never mutates state.
    """
    write_routes = [
        route.path for route in _api_routes(app) if (route.methods or set()) & WRITE_METHODS
    ]
    assert write_routes == ["/api/v1/observations"], (
        f"the only public write path in Stage 0 is observation submission; found: {write_routes}"
    )

    belief = _belief()
    with pytest.raises(ValidationError):
        belief.confidence = ConfidenceComponents(explanation="llm override")  # type: ignore[misc]


def test_public_api_is_versioned(app: FastAPI) -> None:
    unversioned = [
        route.path for route in _api_routes(app) if not route.path.startswith("/api/v1/")
    ]
    assert not unversioned, f"all public endpoints must live under /api/v1: {unversioned}"
