"""Versioned event catalog (Stage 1 §9).

Every event type the Engine may append MUST be registered here with its
schema version, aggregate type, payload schema and governance metadata.
Arbitrary event types are rejected: the event store validates every payload
against this catalog before persisting.

`ObservationAccepted` 1.0 keeps its Stage 0 payload (the Observation contract)
for backward compatibility.
"""

from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, ValidationError

from intelligence_maxxxing.application.errors import (
    EventPayloadInvalidError,
    UnregisteredEventTypeError,
)
from intelligence_maxxxing.contracts.events.epistemic_events import (
    BeliefCreatedPayload,
    BeliefUpdatedPayload,
    EvidenceEvaluatedPayload,
    ExperimentCompletedPayload,
    ExperimentExpiredInconclusivePayload,
    ExperimentObservationWindowOpenedPayload,
    ExperimentRegisteredPayload,
    HypothesisActivatedPayload,
    HypothesisProposedPayload,
    HypothesisRetiredPayload,
    LearningRecordedPayload,
    OutcomeEvaluatedPayload,
)
from intelligence_maxxxing.contracts.events.governance_events import (
    IntegrityCheckCompletedPayload,
    IntegrityStreamQuarantinedPayload,
    IntegrityStreamReleasedPayload,
    IntegrityStreamVerifiedPayload,
    IntegrityViolationDetectedPayload,
    ProjectionCheckpointCreatedPayload,
    ProjectionRebuiltPayload,
)
from intelligence_maxxxing.contracts.events.identity_events import (
    ApplicationCredentialCreatedPayload,
    ApplicationCredentialRevokedPayload,
    ApplicationCredentialRotatedPayload,
    ApplicationRegisteredPayload,
    PermissionGrantedPayload,
    PermissionRevokedPayload,
    UserRegisteredPayload,
)
from intelligence_maxxxing.contracts.events.observation_events import (
    OBSERVATION_ACCEPTED_EVENT_TYPE,
    ObservationAcceptedPayload,
)


class EventSensitivity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EventRetention(StrEnum):
    PERMANENT = "PERMANENT"  # ledger history: never deleted


class EventTypeSpec(BaseModel):
    """Declaration of one (event_type, schema_version) pair."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    event_type: str
    schema_version: str
    aggregate_type: str
    payload_model: type[BaseModel]
    owner: str  # governance owner of the definition
    sensitivity: EventSensitivity
    retention: EventRetention
    producing_use_case: str
    permitted_consumers: tuple[str, ...]


def _spec(
    event_type: str,
    aggregate_type: str,
    payload_model: type[BaseModel],
    producing_use_case: str,
    sensitivity: EventSensitivity = EventSensitivity.MEDIUM,
    permitted_consumers: tuple[str, ...] = ("engine.projections", "engine.audit"),
    schema_version: str = "1.0",
) -> EventTypeSpec:
    return EventTypeSpec(
        event_type=event_type,
        schema_version=schema_version,
        aggregate_type=aggregate_type,
        payload_model=payload_model,
        owner="engine.core",
        sensitivity=sensitivity,
        retention=EventRetention.PERMANENT,
        producing_use_case=producing_use_case,
        permitted_consumers=permitted_consumers,
    )


_SPECS: Final[tuple[EventTypeSpec, ...]] = (
    _spec(
        "ApplicationRegistered",
        "Application",
        ApplicationRegisteredPayload,
        "identity.register_application",
    ),
    _spec(
        "ApplicationCredentialCreated",
        "ApplicationCredential",
        ApplicationCredentialCreatedPayload,
        "identity.create_credential",
        sensitivity=EventSensitivity.HIGH,
    ),
    _spec(
        "ApplicationCredentialRotated",
        "ApplicationCredential",
        ApplicationCredentialRotatedPayload,
        "identity.rotate_credential",
        sensitivity=EventSensitivity.HIGH,
    ),
    _spec(
        "ApplicationCredentialRevoked",
        "ApplicationCredential",
        ApplicationCredentialRevokedPayload,
        "identity.revoke_credential",
        sensitivity=EventSensitivity.HIGH,
    ),
    _spec("UserRegistered", "User", UserRegisteredPayload, "identity.bootstrap_owner"),
    _spec(
        "PermissionGranted",
        "Application",
        PermissionGrantedPayload,
        "identity.grant_scope",
        sensitivity=EventSensitivity.HIGH,
    ),
    _spec(
        "PermissionRevoked",
        "Application",
        PermissionRevokedPayload,
        "identity.revoke_scope",
        sensitivity=EventSensitivity.HIGH,
    ),
    _spec(
        OBSERVATION_ACCEPTED_EVENT_TYPE,
        "Observation",
        ObservationAcceptedPayload,
        "observations.submit",
    ),
    _spec(
        "ProjectionRebuilt",
        "Projection",
        ProjectionRebuiltPayload,
        "projections.rebuild",
        sensitivity=EventSensitivity.LOW,
    ),
    _spec(
        "ProjectionCheckpointCreated",
        "Projection",
        ProjectionCheckpointCreatedPayload,
        "projections.checkpoint",
        sensitivity=EventSensitivity.LOW,
    ),
    _spec(
        "IntegrityCheckCompleted",
        "IntegrityCheck",
        IntegrityCheckCompletedPayload,
        "integrity.verify",
        sensitivity=EventSensitivity.LOW,
    ),
    _spec(
        "IntegrityViolationDetected",
        "IntegrityCheck",
        IntegrityViolationDetectedPayload,
        "integrity.verify",
        sensitivity=EventSensitivity.HIGH,
    ),
    _spec(
        "IntegrityStreamQuarantined",
        "IntegrityStream",
        IntegrityStreamQuarantinedPayload,
        "integrity.verify",
        sensitivity=EventSensitivity.HIGH,
    ),
    _spec(
        "IntegrityStreamVerified",
        "IntegrityStream",
        IntegrityStreamVerifiedPayload,
        "integrity.verify_stream",
        sensitivity=EventSensitivity.MEDIUM,
    ),
    _spec(
        "IntegrityStreamReleased",
        "IntegrityStream",
        IntegrityStreamReleasedPayload,
        "integrity.unquarantine_stream",
        sensitivity=EventSensitivity.HIGH,
    ),
    # --- Stage 3 first epistemic loop -----------------------------------------
    _spec(
        "HypothesisProposed",
        "Hypothesis",
        HypothesisProposedPayload,
        "hypotheses.propose",
    ),
    _spec(
        "HypothesisActivated",
        "Hypothesis",
        HypothesisActivatedPayload,
        "hypotheses.activate",
    ),
    _spec(
        "HypothesisRetired",
        "Hypothesis",
        HypothesisRetiredPayload,
        "hypotheses.retire",
    ),
    _spec(
        "ExperimentRegistered",
        "Experiment",
        ExperimentRegisteredPayload,
        "hypotheses.activate",
    ),
    _spec(
        "ExperimentObservationWindowOpened",
        "Experiment",
        ExperimentObservationWindowOpenedPayload,
        "hypotheses.activate",
    ),
    _spec(
        "EvidenceEvaluated",
        "Evidence",
        EvidenceEvaluatedPayload,
        "experiments.evaluate",
    ),
    _spec(
        "BeliefCreated",
        "Belief",
        BeliefCreatedPayload,
        "experiments.evaluate",
        permitted_consumers=("engine.projections", "engine.audit"),
    ),
    _spec(
        "BeliefUpdated",
        "Belief",
        BeliefUpdatedPayload,
        "experiments.evaluate",
        permitted_consumers=("engine.projections", "engine.audit"),
    ),
    _spec(
        "OutcomeEvaluated",
        "Outcome",
        OutcomeEvaluatedPayload,
        "experiments.evaluate",
    ),
    _spec(
        "LearningRecorded",
        "Learning",
        LearningRecordedPayload,
        "experiments.evaluate",
    ),
    _spec(
        "ExperimentCompleted",
        "Experiment",
        ExperimentCompletedPayload,
        "experiments.evaluate",
    ),
    _spec(
        "ExperimentExpiredInconclusive",
        "Experiment",
        ExperimentExpiredInconclusivePayload,
        "experiments.evaluate",
    ),
)

EVENT_CATALOG: Final[dict[tuple[str, str], EventTypeSpec]] = {
    (spec.event_type, spec.schema_version): spec for spec in _SPECS
}


def get_event_spec(event_type: str, schema_version: str) -> EventTypeSpec:
    """Resolve a registered spec or raise a typed error."""
    spec = EVENT_CATALOG.get((event_type, schema_version))
    if spec is None:
        raise UnregisteredEventTypeError(
            f"event type {event_type!r} schema {schema_version!r} is not in the event catalog"
        )
    return spec


def validate_event_payload(
    event_type: str, schema_version: str, payload: dict[str, object]
) -> None:
    """event_type + schema_version -> known schema -> valid payload."""
    spec = get_event_spec(event_type, schema_version)
    try:
        spec.payload_model.model_validate(payload)
    except ValidationError as exc:
        raise EventPayloadInvalidError(
            f"payload for {event_type} {schema_version} does not match its "
            f"catalog schema: {exc.error_count()} validation error(s)"
        ) from exc
