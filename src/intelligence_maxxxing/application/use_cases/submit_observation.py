"""Submit-observation use case (Stage 1: authenticated, scoped, concurrent-safe).

Application -> auth context -> validation -> Observation -> ObservationAccepted
event (catalog-validated, hash-chained) -> AuditRecord (measured health
snapshot) -> idempotency record, all inside one transaction.

Idempotency contract (Engine Service Contract §11 + Stage 1 §3.2):
- effective scope = tenant + owner + application + action + key;
- same scope + same payload   -> return the original result, create nothing;
- same scope + different payload -> deterministic IdempotencyConflictError;
- two CONCURRENT requests with the same scope: exactly one write wins; the
  loser detects the race on commit, re-reads the winner's committed record
  and returns the same result (or a 409 if payloads differ). Never a raw
  IntegrityError, never HTTP 500.
"""

import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field

from intelligence_maxxxing.application.auth.service import AuthContext
from intelligence_maxxxing.application.errors import (
    IdempotencyConflictError,
    IdempotencyRaceDetected,
)
from intelligence_maxxxing.application.ports import (
    HealthSnapshotProviderPort,
    IdempotencyRecord,
    ProjectedObservation,
    UnitOfWorkPort,
)
from intelligence_maxxxing.domain.audit.models import AuditRecord, EngineEvent
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
SUBMIT_OBSERVATION_ACTION = "observations.submit"


class SubmitObservationCommand(BaseModel):
    """Validated intent to register one observation.

    Identity fields are NOT here: they come from the authenticated context
    passed separately, so a request body can never spoof the actor.
    """

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
        exclude={"idempotency_key", "request_id"},
    )
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SubmitObservationUseCase:
    def __init__(
        self,
        uow: UnitOfWorkPort,
        engine_version: str,
        api_version: str,
        health_provider: HealthSnapshotProviderPort,
    ) -> None:
        self._uow = uow
        self._engine_version = engine_version
        self._api_version = api_version
        self._health = health_provider

    def execute(
        self, command: SubmitObservationCommand, auth: AuthContext
    ) -> SubmitObservationResult:
        payload_hash = _payload_hash(command)

        replayed = self._find_existing(command, auth, payload_hash)
        if replayed is not None:
            return replayed

        try:
            return self._write(command, auth, payload_hash)
        except IdempotencyRaceDetected:
            # A concurrent request with the same scope+key committed first.
            # Deterministic resolution: adopt the winner's result (same
            # payload) or surface the same conflict a serial retry would get.
            replayed = self._find_existing(command, auth, payload_hash)
            if replayed is None:
                raise IdempotencyConflictError(
                    "idempotency race detected but winning record not readable"
                ) from None
            return replayed

    def _find_existing(
        self, command: SubmitObservationCommand, auth: AuthContext, payload_hash: str
    ) -> SubmitObservationResult | None:
        with self._uow as uow:
            existing = uow.idempotency.get(
                application_id=auth.application_id,
                owner_id=auth.owner_id,
                action=SUBMIT_OBSERVATION_ACTION,
                idempotency_key=command.idempotency_key,
            )
            uow.commit()
        if existing is None:
            return None
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

    def _write(
        self, command: SubmitObservationCommand, auth: AuthContext, payload_hash: str
    ) -> SubmitObservationResult:
        with self._uow as uow:
            now = utc_now()
            audit_id = new_id(AUDIT_PREFIX)
            event_id = new_id(EVENT_PREFIX)

            context = command.context.model_copy(update={"tenant_id": auth.tenant_id})
            observation = Observation(
                id=new_id(OBSERVATION_PREFIX),
                schema_version=command.schema_version,
                domain_pack=command.domain_pack,
                subject=command.subject,
                statement=command.statement,
                knowledge_class=command.knowledge_class,
                unknown_reason=command.unknown_reason,
                observed_by=command.observed_by,
                context=context,
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
                tenant_id=auth.tenant_id,
                owner_id=auth.owner_id,
                application_id=auth.application_id,
                actor=auth.actor,
                schema_version=CANONICAL_SCHEMA_VERSION,
                payload=observation.model_dump(mode="json"),
                occurred_at=command.occurred_at or now,
                recorded_at=now,
                audit_id=audit_id,
                request_id=command.request_id,
                idempotency_key=command.idempotency_key,
            )
            persisted = uow.events.append_one(event)

            # Keep the read model current inside the same transaction. The
            # projection remains disposable: rebuild_from_zero reproduces it.
            if persisted.global_position is None:
                raise RuntimeError("persisted event missing global_position")
            uow.projections.upsert_observation(
                ProjectedObservation(
                    observation_id=observation.id,
                    global_position=persisted.global_position,
                    event_id=persisted.event_id,
                    tenant_id=auth.tenant_id,
                    owner_id=auth.owner_id,
                    application_id=auth.application_id,
                    domain_pack=command.domain_pack,
                    schema_version=observation.schema_version,
                    subject=observation.subject,
                    statement=observation.statement,
                    knowledge_class=observation.knowledge_class.value,
                    unknown_reason=(
                        observation.unknown_reason.value
                        if observation.unknown_reason is not None
                        else None
                    ),
                    observed_by=observation.observed_by,
                    context=observation.context.model_dump(mode="json"),
                    source_ids=observation.source_ids,
                    metadata=dict(observation.metadata),
                    occurred_at=observation.occurred_at,
                    created_at=observation.created_at,
                    audit_id=audit_id,
                )
            )

            snapshot = self._health.capture()
            audit = AuditRecord(
                audit_id=audit_id,
                request_id=command.request_id,
                engine_version=self._engine_version,
                api_version=self._api_version,
                schema_version=CANONICAL_SCHEMA_VERSION,
                domain_pack=command.domain_pack,
                tenant_id=auth.tenant_id,
                owner_id=auth.owner_id,
                application_id=auth.application_id,
                actor=auth.actor,
                action=SUBMIT_OBSERVATION_ACTION,
                input_object_ids=command.source_ids,
                output_object_ids=(observation.id,),
                event_ids=(event_id,),
                timestamp=now,
                health_state=snapshot.model_dump(mode="json"),
            )
            uow.audits.append(audit)

            uow.idempotency.put(
                IdempotencyRecord(
                    tenant_id=auth.tenant_id,
                    owner_id=auth.owner_id,
                    application_id=auth.application_id,
                    actor_id=auth.actor.actor_id,
                    action=SUBMIT_OBSERVATION_ACTION,
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
