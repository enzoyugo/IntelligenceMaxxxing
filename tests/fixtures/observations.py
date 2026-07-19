"""Synthetic observation fixtures. No real personal data, no external systems."""

from typing import Any


def observed_fact_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "domain_pack": "core",
        "subject": "hydration",
        "statement": "Drank 2.0 liters of water",
        "knowledge_class": "OBSERVED_FACT",
        "observed_by": "fixture",
        "context": {"scope": "personal", "attributes": {}},
        "source_ids": [],
        "metadata": {"unit": "liters"},
    }
    payload.update(overrides)
    return payload


def unknown_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "domain_pack": "core",
        "subject": "stress",
        "statement": "Stress level could not be measured today",
        "knowledge_class": "UNKNOWN",
        "unknown_reason": "NOT_MEASURABLE_DIRECTLY",
        "observed_by": "fixture",
        "context": {"scope": "personal", "attributes": {}},
        "source_ids": [],
        "metadata": {},
    }
    payload.update(overrides)
    return payload
