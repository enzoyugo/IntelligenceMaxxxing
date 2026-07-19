"""Unit tests for canonical domain objects."""

import pytest
from pydantic import ValidationError

from intelligence_maxxxing.domain.common.base import Context, utc_now
from intelligence_maxxxing.domain.common.confidence import ConfidenceComponents
from intelligence_maxxxing.domain.common.epistemic import (
    ConfidenceLevel,
    KnowledgeClass,
    UnknownReason,
)
from intelligence_maxxxing.domain.common.health import (
    ComponentHealth,
    HealthState,
    HealthStatus,
)
from intelligence_maxxxing.domain.observations import Observation


def _context() -> Context:
    return Context(scope="personal")


def _observation(**overrides: object) -> Observation:
    defaults: dict[str, object] = {
        "id": "obs_" + "0" * 32,
        "schema_version": "1.0",
        "subject": "sleep",
        "statement": "slept 8 hours",
        "knowledge_class": KnowledgeClass.OBSERVED_FACT,
        "observed_by": "human",
        "context": _context(),
        "created_at": utc_now(),
        "audit_id": "aud_" + "0" * 32,
    }
    defaults.update(overrides)
    return Observation(**defaults)  # type: ignore[arg-type]


class TestObservation:
    def test_valid_observation(self) -> None:
        obs = _observation()
        assert obs.knowledge_class is KnowledgeClass.OBSERVED_FACT

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            _observation(surprise="not allowed")

    def test_frozen(self) -> None:
        obs = _observation()
        with pytest.raises(ValidationError):
            obs.subject = "changed"  # type: ignore[misc]

    def test_naive_timestamp_rejected(self) -> None:
        from datetime import datetime

        with pytest.raises(ValidationError):
            _observation(created_at=datetime(2026, 1, 1))

    def test_unknown_requires_reason(self) -> None:
        with pytest.raises(ValidationError):
            _observation(knowledge_class=KnowledgeClass.UNKNOWN)

    def test_unknown_with_reason_is_valid(self) -> None:
        obs = _observation(
            knowledge_class=KnowledgeClass.UNKNOWN,
            unknown_reason=UnknownReason.MISSING_DATA,
        )
        assert obs.unknown_reason is UnknownReason.MISSING_DATA

    def test_inference_cannot_be_observation(self) -> None:
        with pytest.raises(ValidationError):
            _observation(knowledge_class=KnowledgeClass.INFERENCE)

    def test_metadata_size_is_limited(self) -> None:
        oversized = {f"key_{i}": i for i in range(50)}
        with pytest.raises(ValidationError):
            _observation(metadata=oversized)


class TestConfidence:
    def test_interval_must_be_ordered(self) -> None:
        with pytest.raises(ValidationError):
            ConfidenceComponents(interval_low=0.9, interval_high=0.1)

    def test_partial_interval_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ConfidenceComponents(interval_low=0.1)

    def test_components_are_separable(self) -> None:
        confidence = ConfidenceComponents(
            data_confidence=ConfidenceLevel.HIGH,
            method_confidence=ConfidenceLevel.LOW,
            conclusion_confidence=ConfidenceLevel.MODERATE,
            recommendation_confidence=ConfidenceLevel.VERY_LOW,
        )
        assert confidence.data_confidence is not confidence.method_confidence


class TestHealthAggregation:
    def test_worst_state_wins(self) -> None:
        status = HealthStatus.aggregate(
            (
                ComponentHealth(component="api", state=HealthState.HEALTHY),
                ComponentHealth(component="database", state=HealthState.UNHEALTHY),
            )
        )
        assert status.status is HealthState.UNHEALTHY

    def test_all_healthy(self) -> None:
        status = HealthStatus.aggregate(
            (ComponentHealth(component="api", state=HealthState.HEALTHY),)
        )
        assert status.status is HealthState.HEALTHY
