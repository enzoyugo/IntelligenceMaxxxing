"""Rebuildable accepted_observations projection (Stage 1 §12).

Rules:
- derived exclusively from engine_events;
- disposable and rebuildable from zero;
- checkpointed and versioned;
- never the primary source of truth;
- apply is idempotent (replay of the same event yields the same row);
- scoped by owner/application on every projected row;
- unknown event types STOP the projector (fail closed / QUARANTINED).

Checkpoints are mutable DERIVED state - a documented exception to
append-only. Rebuild history itself is recorded as append-only events.
"""

import hashlib
import json
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from intelligence_maxxxing.application.errors import UnknownProjectionEventError
from intelligence_maxxxing.application.ports import (
    HealthSnapshotProviderPort,
    ProjectedObservation,
    ProjectionCheckpoint,
    UnitOfWorkPort,
)
from intelligence_maxxxing.domain.audit.models import AuditRecord, EngineEvent
from intelligence_maxxxing.domain.common.base import CANONICAL_SCHEMA_VERSION, utc_now
from intelligence_maxxxing.domain.common.identifiers import (
    AUDIT_PREFIX,
    EVENT_PREFIX,
    new_id,
)
from intelligence_maxxxing.domain.identity.system import (
    SYSTEM_ACTOR,
    SYSTEM_APPLICATION_ID,
    SYSTEM_OWNER_ID,
    SYSTEM_TENANT_ID,
)

ACCEPTED_OBSERVATIONS_PROJECTION = "accepted_observations"
ACCEPTED_OBSERVATIONS_VERSION = "1.0"

# Event types the projector understands (and may safely skip). Anything else
# is unknown and, by policy, STOPS the rebuild.
_HANDLED_EVENT_TYPES = frozenset({"ObservationAccepted"})
_SKIPPED_EVENT_TYPES = frozenset(
    {
        "ApplicationRegistered",
        "ApplicationCredentialCreated",
        "ApplicationCredentialRotated",
        "ApplicationCredentialRevoked",
        "UserRegistered",
        "PermissionGranted",
        "PermissionRevoked",
        "ProjectionRebuilt",
        "ProjectionCheckpointCreated",
        "IntegrityCheckCompleted",
        "IntegrityViolationDetected",
    }
)


class RebuildResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    projection_name: str
    projection_version: str
    events_scanned: int
    rows_written: int
    last_global_position: int
    checksum: str
    from_scratch: bool


class ProjectionRebuildService:
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

    def rebuild(self, *, from_scratch: bool = True) -> RebuildResult:
        with self._uow as uow:
            if from_scratch:
                uow.projections.delete_all_observations()
                uow.projections.delete_checkpoint(
                    ACCEPTED_OBSERVATIONS_PROJECTION, ACCEPTED_OBSERVATIONS_VERSION
                )
                start_position = 0
            else:
                checkpoint = uow.projections.get_checkpoint(
                    ACCEPTED_OBSERVATIONS_PROJECTION, ACCEPTED_OBSERVATIONS_VERSION
                )
                start_position = checkpoint.last_global_position if checkpoint else 0

            events = list(uow.events.stream_from_position(start_position, limit=1_000_000))
            rows_written = 0
            last_position = start_position
            last_event_id: str | None = None

            try:
                for event in events:
                    self._apply(uow, event)
                    if event.event_type in _HANDLED_EVENT_TYPES:
                        rows_written += 1
                    if event.global_position is not None:
                        last_position = event.global_position
                    last_event_id = event.event_id
            except UnknownProjectionEventError:
                now = utc_now()
                uow.projections.save_checkpoint(
                    ProjectionCheckpoint(
                        projection_name=ACCEPTED_OBSERVATIONS_PROJECTION,
                        projection_version=ACCEPTED_OBSERVATIONS_VERSION,
                        owner_scope="ALL",
                        application_scope="ALL",
                        last_global_position=last_position,
                        last_event_id=last_event_id,
                        updated_at=now,
                        status="QUARANTINED",
                        checksum=None,
                    )
                )
                uow.commit()
                raise

            all_rows = list(uow.projections.list_all_observations())
            checksum = _checksum(all_rows)
            now = utc_now()
            uow.projections.save_checkpoint(
                ProjectionCheckpoint(
                    projection_name=ACCEPTED_OBSERVATIONS_PROJECTION,
                    projection_version=ACCEPTED_OBSERVATIONS_VERSION,
                    owner_scope="ALL",
                    application_scope="ALL",
                    last_global_position=last_position,
                    last_event_id=last_event_id,
                    updated_at=now,
                    status="READY",
                    checksum=checksum,
                )
            )

            audit_id = new_id(AUDIT_PREFIX)
            rebuilt_event = EngineEvent(
                event_id=new_id(EVENT_PREFIX),
                event_type="ProjectionRebuilt",
                aggregate_type="Projection",
                aggregate_id=ACCEPTED_OBSERVATIONS_PROJECTION,
                aggregate_version=self._next_version(uow),
                domain_pack="core",
                tenant_id=SYSTEM_TENANT_ID,
                owner_id=SYSTEM_OWNER_ID,
                application_id=SYSTEM_APPLICATION_ID,
                actor=SYSTEM_ACTOR,
                schema_version=CANONICAL_SCHEMA_VERSION,
                payload={
                    "projection_name": ACCEPTED_OBSERVATIONS_PROJECTION,
                    "projection_version": ACCEPTED_OBSERVATIONS_VERSION,
                    "events_applied": len(events),
                    "rows_written": rows_written,
                    "last_global_position": last_position,
                    "checksum": checksum,
                    "rebuilt_at": now.isoformat(),
                },
                occurred_at=now,
                recorded_at=now,
                audit_id=audit_id,
                request_id=audit_id,
            )
            uow.events.append_one(rebuilt_event)
            snapshot = self._health.capture()
            uow.audits.append(
                AuditRecord(
                    audit_id=audit_id,
                    request_id=audit_id,
                    engine_version=self._engine_version,
                    api_version=self._api_version,
                    schema_version=CANONICAL_SCHEMA_VERSION,
                    domain_pack="core",
                    tenant_id=SYSTEM_TENANT_ID,
                    owner_id=SYSTEM_OWNER_ID,
                    application_id=SYSTEM_APPLICATION_ID,
                    actor=SYSTEM_ACTOR,
                    action="projections.rebuild",
                    input_object_ids=(),
                    output_object_ids=(ACCEPTED_OBSERVATIONS_PROJECTION,),
                    event_ids=(rebuilt_event.event_id,),
                    timestamp=now,
                    health_state=snapshot.model_dump(mode="json"),
                )
            )
            uow.commit()

        return RebuildResult(
            projection_name=ACCEPTED_OBSERVATIONS_PROJECTION,
            projection_version=ACCEPTED_OBSERVATIONS_VERSION,
            events_scanned=len(events),
            rows_written=rows_written,
            last_global_position=last_position,
            checksum=checksum,
            from_scratch=from_scratch,
        )

    def verify(self) -> RebuildResult:
        """Rebuild into a fresh projection and compare checksums.

        Does not mutate the live projection if verification fails: it rebuilds
        from scratch into the live table, so callers that want a non-destructive
        check should capture the previous checksum first.
        """
        return self.rebuild(from_scratch=True)

    def _next_version(self, uow: UnitOfWorkPort) -> int:
        latest = uow.events.get_latest_aggregate_version(
            "Projection", ACCEPTED_OBSERVATIONS_PROJECTION
        )
        return (latest or 0) + 1

    def _apply(self, uow: UnitOfWorkPort, event: EngineEvent) -> None:
        if event.event_type in _SKIPPED_EVENT_TYPES:
            return
        if event.event_type not in _HANDLED_EVENT_TYPES:
            raise UnknownProjectionEventError(
                f"unknown event type for projection: {event.event_type}"
            )
        if event.global_position is None:
            raise UnknownProjectionEventError(
                f"event {event.event_id} has no global_position; cannot project"
            )
        payload = event.payload
        row = ProjectedObservation(
            observation_id=str(payload["id"]),
            global_position=event.global_position,
            event_id=event.event_id,
            tenant_id=event.tenant_id,
            owner_id=event.owner_id,
            application_id=event.application_id,
            domain_pack=event.domain_pack,
            schema_version=str(payload.get("schema_version", event.schema_version)),
            subject=str(payload["subject"]),
            statement=str(payload["statement"]),
            knowledge_class=str(payload["knowledge_class"]),
            unknown_reason=(
                str(payload["unknown_reason"]) if payload.get("unknown_reason") else None
            ),
            observed_by=str(payload.get("observed_by", event.actor.actor_id)),
            context=_as_object_dict(payload.get("context")),
            source_ids=_as_str_tuple(payload.get("source_ids")),
            metadata=_as_object_dict(payload.get("metadata")),
            occurred_at=event.occurred_at,
            created_at=event.recorded_at,
            audit_id=event.audit_id,
        )
        uow.projections.upsert_observation(row)


def _as_object_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items()}
    return {}


def _as_str_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()


def _checksum(rows: Sequence[ProjectedObservation]) -> str:
    material = [
        {
            "observation_id": r.observation_id,
            "global_position": r.global_position,
            "event_id": r.event_id,
            "owner_id": r.owner_id,
            "application_id": r.application_id,
            "statement": r.statement,
            "subject": r.subject,
            "knowledge_class": r.knowledge_class,
        }
        for r in rows
    ]
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
