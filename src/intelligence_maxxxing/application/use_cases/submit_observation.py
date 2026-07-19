"""Submit-observation use case: the Stage 0 smoke path.

Application -> validation -> Observation -> ObservationAccepted event ->
AuditRecord -> idempotency record, all inside one transaction.

Idempotency contract (Engine Service Contract §11):
- same key + same payload  -> return the original result, create nothing new;
- same key + different payload -> explicit IdempotencyConflictError.
"""

import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field

from intelligence_maxxxing.application.errors import IdempotencyConflictError
from intelligence_maxxxing.application.ports import IdempotencyRecord, UnitOfWorkPort
from intelligence_maxxxing.domain.audit.models import Actor, AuditRecord, EngineEvent
from intelligence_maxxxing.domain.common.base import (
    CANONICAL_SCHEMA_VERSION,
    Context,
    LimitedMetadata,
    SchemaVersion,
    UtcDatetime,
    utc_now,
)
from intelligence_maxxxing.domain.common.epistemic import KnowledgeClass, UnknownReason
from intelligence_maxxxing.domain.common.identifiers import (
    AUDIT_PREFIX,
    EVENT_PREFIX,
    OBSERVATION_PREFIX,
    new_id,
)
from intelligence_maxxxing.domain.observations import Observation

OBSERVATION_ACCEPTED_EVENT = "ObservationAccepted"
OBSERVATION_AGGREGATE_TYPE = "Observation"
_IDEMPOTENCY_SCOPE = "observations.submit"


class SubmitObservationCommand(BaseModel):
    """Validated intent to register one observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: SchemaVersion
    domain_pack: str = Field(default="core", min_length=1)
    subject: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    knowledge_class: KnowledgeClass
    unknown_reason: UnknownReason | None = None
    observed_by: str = Field(min_length=1)
    context: Context
    occurred_at: UtcDatetime | None = None
    source_ids: tuple[str, ...] = ()
    metadata: LimitedMetadata = Field(default_factory=dict)

    idempotency_key: str = Field(min_length=1, max_length=256)
    request_id: str = Field(min_length=1)
    actor: Actor


class SubmitObservationResult(BaseModel):
    """Outcome of an accepted (or safely replayed) observation submission."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str
    event_id: str
    audit_id: str
    replayed: bool


def _payload_hash(command: SubmitObservationCommand) -> str:
    """Canonical hash of the client-controlled payload (excludes retry-variant fields)."""
    material = command.model_dump(
        mode="json",
        exclude={"idempotency_key", "request_id", "actor"},
    )
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SubmitObservationUseCase:
    def __init__(self, uow: UnitOfWorkPort, engine_version: str, api_version: str) -> None:
        self._uow = uow
        self._engine_version = engine_version
        self._api_version = api_version

    def execute(self, command: SubmitObservationCommand) -> SubmitObservationResult:
        payload_hash = _payload_hash(command)

        with self._uow as uow:
            existing = uow.idempotency.get(_IDEMPOTENCY_SCOPE, command.idempotency_key)
            if existing is not None:
                if existing.payload_hash != payload_hash:
                    raise IdempotencyConflictError(
                        "idempotency key was already used with a different payload"
                    )
                return SubmitObservationResult(
                    observation_id=existing.observation_id,
                    event_id=existing.event_id,
                    audit_id=existing.audit_id,
                    replayed=True,
                )

            now = utc_now()
            audit_id = new_id(AUDIT_PREFIX)
            event_id = new_id(EVENT_PREFIX)

            observation = Observation(
                id=new_id(OBSERVATION_PREFIX),
                schema_version=command.schema_version,
                domain_pack=command.domain_pack,
                subject=command.subject,
                statement=command.statement,
                knowledge_class=command.knowledge_class,
                unknown_reason=command.unknown_reason,
                observed_by=command.observed_by,
                context=command.context,
                created_at=now,
                occurred_at=command.occurred_at,
                source_ids=command.source_ids,
                metadata=command.metadata,
                audit_id=audit_id,
            )

            event = EngineEvent(
                event_id=event_id,
                event_type=OBSERVATION_ACCEPTED_EVENT,
                aggregate_type=OBSERVATION_AGGREGATE_TYPE,
                aggregate_id=observation.id,
                aggregate_version=1,
                domain_pack=command.domain_pack,
                actor=command.actor,
                schema_version=CANONICAL_SCHEMA_VERSION,
                payload=observation.model_dump(mode="json"),
                occurred_at=command.occurred_at or now,
                recorded_at=now,
                audit_id=audit_id,
                request_id=command.request_id,
                idempotency_key=command.idempotency_key,
            )
            uow.events.append(event)

            audit = AuditRecord(
                audit_id=audit_id,
                request_id=command.request_id,
                engine_version=self._engine_version,
                api_version=self._api_version,
                schema_version=CANONICAL_SCHEMA_VERSION,
                domain_pack=command.domain_pack,
                actor=command.actor,
                action="observations.submit",
                input_object_ids=command.source_ids,
                output_object_ids=(observation.id,),
                event_ids=(event_id,),
                timestamp=now,
                health_state={"api": "HEALTHY", "database": "HEALTHY"},
            )
            uow.audits.append(audit)

            uow.idempotency.put(
                IdempotencyRecord(
                    scope=_IDEMPOTENCY_SCOPE,
                    idempotency_key=command.idempotency_key,
                    payload_hash=payload_hash,
                    observation_id=observation.id,
                    event_id=event_id,
                    audit_id=audit_id,
                )
            )

            uow.commit()

        return SubmitObservationResult(
            observation_id=observation.id,
            event_id=event_id,
            audit_id=audit_id,
            replayed=False,
        )
