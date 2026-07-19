"""Event catalog tests.

UNREGISTERED_EVENT_TYPE_REJECTED / WRONG_EVENT_SCHEMA_REJECTED /
OBSERVATION_ACCEPTED_V1_BACKWARD_COMPATIBLE
"""

import pytest

from intelligence_maxxxing.application.errors import (
    EventPayloadInvalidError,
    UnregisteredEventTypeError,
)
from intelligence_maxxxing.contracts.events.catalog import (
    EVENT_CATALOG,
    validate_event_payload,
)
from intelligence_maxxxing.domain.common.base import utc_now
from intelligence_maxxxing.domain.common.epistemic import KnowledgeClass


def test_unregistered_event_type_rejected() -> None:
    with pytest.raises(UnregisteredEventTypeError):
        validate_event_payload("TotallyUnknownEvent", "1.0", {})


def test_wrong_event_schema_rejected() -> None:
    with pytest.raises(EventPayloadInvalidError):
        validate_event_payload(
            "ApplicationRegistered",
            "1.0",
            {"application_id": "app_x"},  # missing required fields
        )


def test_observation_accepted_v1_backward_compatible() -> None:
    assert ("ObservationAccepted", "1.0") in EVENT_CATALOG
    now = utc_now().isoformat()
    payload = {
        "id": "obs_" + "0" * 32,
        "schema_version": "1.0",
        "domain_pack": "core",
        "subject": "sleep",
        "context": {"schema_version": "1.0", "scope": "personal", "tenant_id": "tnt_x"},
        "created_at": now,
        "source_ids": [],
        "metadata": {},
        "knowledge_class": KnowledgeClass.OBSERVED_FACT.value,
        "statement": "Slept 7 hours",
        "audit_id": "aud_" + "0" * 32,
        "observed_by": "human",
    }
    validate_event_payload("ObservationAccepted", "1.0", payload)
