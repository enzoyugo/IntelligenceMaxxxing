"""Production ingest must refuse smoke purposes without TEST environment."""

from __future__ import annotations

import pytest

from intelligence_maxxxing.application.errors import EventPayloadInvalidError
from intelligence_maxxxing.application.use_cases.submit_observation import (
    SubmitObservationCommand,
    _reject_test_purpose_on_production_context,
)
from intelligence_maxxxing.domain.common.base import Context
from intelligence_maxxxing.domain.common.epistemic import KnowledgeClass


def _cmd(*, purpose: str, environment: str | None) -> SubmitObservationCommand:
    return SubmitObservationCommand(
        schema_version="1.0",
        domain_pack="life",
        subject="daily_check_in",
        statement="Daily check-in completed",
        knowledge_class=KnowledgeClass.OBSERVED_FACT,
        observed_by="test",
        context=Context(scope="personal", environment=environment, attributes={}),
        metadata={
            "life_event_type": "life.daily_check_in.completed.v1",
            "observation_purpose": purpose,
        },
        idempotency_key="k1",
        request_id="r1",
    )


def test_smoke_on_production_rejected() -> None:
    with pytest.raises(EventPayloadInvalidError):
        _reject_test_purpose_on_production_context(
            _cmd(purpose="SMOKE_TEST", environment="PRODUCTION")
        )


def test_smoke_without_environment_rejected() -> None:
    with pytest.raises(EventPayloadInvalidError):
        _reject_test_purpose_on_production_context(
            _cmd(purpose="SMOKE_TEST", environment=None)
        )


def test_smoke_on_test_environment_allowed() -> None:
    _reject_test_purpose_on_production_context(
        _cmd(purpose="SMOKE_TEST", environment="TEST")
    )


def test_user_observation_on_production_allowed() -> None:
    _reject_test_purpose_on_production_context(
        _cmd(purpose="USER_OBSERVATION", environment="PRODUCTION")
    )
