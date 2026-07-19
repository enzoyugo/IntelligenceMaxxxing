"""Integrity chain verification (Stage 1 §11).

Chain scope: per (owner_id, application_id) stream. Full and incremental
modes are supported. A broken chain emits IntegrityViolationDetected and
invokes the kill-switch hook. This is tamper/corruption DETECTION, not
absolute cryptographic security.
"""

from pydantic import BaseModel, ConfigDict

from intelligence_maxxxing.application.ports import (
    HealthSnapshotProviderPort,
    IntegrityViolationHookPort,
    UnitOfWorkPort,
)
from intelligence_maxxxing.domain.audit.integrity import verify_chain
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


class StreamViolation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    owner_id: str
    application_id: str
    broken_event_id: str


class IntegrityReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: str
    streams_checked: int
    events_checked: int
    violations: tuple[StreamViolation, ...] = ()
    ok: bool


class IntegrityVerificationService:
    def __init__(
        self,
        uow: UnitOfWorkPort,
        engine_version: str,
        api_version: str,
        health_provider: HealthSnapshotProviderPort,
        violation_hook: IntegrityViolationHookPort,
    ) -> None:
        self._uow = uow
        self._engine_version = engine_version
        self._api_version = api_version
        self._health = health_provider
        self._hook = violation_hook

    def verify(self, *, mode: str = "FULL", since_position: int = 0) -> IntegrityReport:
        if mode not in {"FULL", "INCREMENTAL"}:
            raise ValueError("mode must be FULL or INCREMENTAL")

        with self._uow as uow:
            stream_keys = list(uow.events.list_stream_keys())
            violations: list[StreamViolation] = []
            events_checked = 0

            for owner_id, application_id in stream_keys:
                events = list(
                    uow.events.stream_for_stream_key(
                        owner_id, application_id, from_position=since_position
                    )
                )
                events_checked += len(events)
                ok, broken = verify_chain(list(events))
                if not ok and broken is not None:
                    violations.append(
                        StreamViolation(
                            owner_id=owner_id,
                            application_id=application_id,
                            broken_event_id=broken,
                        )
                    )

            now = utc_now()
            audit_id = new_id(AUDIT_PREFIX)
            completed = EngineEvent(
                event_id=new_id(EVENT_PREFIX),
                event_type="IntegrityCheckCompleted",
                aggregate_type="IntegrityCheck",
                aggregate_id=f"integrity_{now.strftime('%Y%m%d%H%M%S')}",
                aggregate_version=1,
                domain_pack="core",
                tenant_id=SYSTEM_TENANT_ID,
                owner_id=SYSTEM_OWNER_ID,
                application_id=SYSTEM_APPLICATION_ID,
                actor=SYSTEM_ACTOR,
                schema_version=CANONICAL_SCHEMA_VERSION,
                payload={
                    "streams_checked": len(stream_keys),
                    "events_checked": events_checked,
                    "violations_found": len(violations),
                    "mode": mode,
                    "completed_at": now.isoformat(),
                },
                occurred_at=now,
                recorded_at=now,
                audit_id=audit_id,
                request_id=audit_id,
            )
            uow.events.append_one(completed)

            for violation in violations:
                self._hook.on_violation(
                    violation.owner_id, violation.application_id, violation.broken_event_id
                )
                alert = EngineEvent(
                    event_id=new_id(EVENT_PREFIX),
                    event_type="IntegrityViolationDetected",
                    aggregate_type="IntegrityCheck",
                    aggregate_id=f"integrity_violation_{violation.broken_event_id}",
                    aggregate_version=1,
                    domain_pack="core",
                    tenant_id=SYSTEM_TENANT_ID,
                    owner_id=SYSTEM_OWNER_ID,
                    application_id=SYSTEM_APPLICATION_ID,
                    actor=SYSTEM_ACTOR,
                    schema_version=CANONICAL_SCHEMA_VERSION,
                    payload={
                        "stream_owner_id": violation.owner_id,
                        "stream_application_id": violation.application_id,
                        "broken_event_id": violation.broken_event_id,
                        "detected_at": now.isoformat(),
                    },
                    occurred_at=now,
                    recorded_at=now,
                    audit_id=audit_id,
                    request_id=audit_id,
                )
                uow.events.append_one(alert)

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
                    action="integrity.verify",
                    input_object_ids=(),
                    output_object_ids=tuple(v.broken_event_id for v in violations),
                    event_ids=(completed.event_id,),
                    timestamp=now,
                    health_state=snapshot.model_dump(mode="json"),
                )
            )
            uow.commit()

        return IntegrityReport(
            mode=mode,
            streams_checked=len(stream_keys),
            events_checked=events_checked,
            violations=tuple(violations),
            ok=len(violations) == 0,
        )


class LoggingIntegrityViolationHook(IntegrityViolationHookPort):
    """Default kill-switch hook: structured log. Future stages can escalate
    to pausing writes for the broken stream."""

    def on_violation(self, owner_id: str, application_id: str, broken_event_id: str) -> None:
        from intelligence_maxxxing.observability.logging import get_logger

        get_logger("intelligence_maxxxing.integrity").error(
            "integrity violation detected",
            extra={
                "owner_id": owner_id,
                "application_id": application_id,
                "broken_event_id": broken_event_id,
            },
        )


class NoOpIntegrityViolationHook(IntegrityViolationHookPort):
    """Test-friendly hook that records calls without side effects."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def on_violation(self, owner_id: str, application_id: str, broken_event_id: str) -> None:
        self.calls.append((owner_id, application_id, broken_event_id))


class MigrationSafetyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    destructive_migrations_allowed: bool = False
    maintenance_mode: bool = False
    confirmed_backup_id: str | None = None
    actor_has_administer: bool = False
    confirm_phrase: str | None = None


REQUIRED_CONFIRM_PHRASE = "I UNDERSTAND THIS DESTROYS HISTORY"


class MigrationSafetyPolicy:
    """Blocks destructive downgrades by default (Stage 1 §3.4 / §16).

    All of the following must be true for a destructive downgrade to proceed:
    - ENGINE_DESTRUCTIVE_MIGRATIONS_ALLOWED=true
    - ENGINE_MAINTENANCE_MODE=true
    - ENGINE_CONFIRMED_BACKUP_ID is a non-empty verified backup id
    - the actor holds ADMINISTER_ENGINE
    - the confirm phrase matches exactly
    """

    def authorize(self, request: MigrationSafetyRequest) -> list[str]:
        """Return a list of blocking reasons. Empty list means authorized."""
        blockers: list[str] = []
        if not request.destructive_migrations_allowed:
            blockers.append("ENGINE_DESTRUCTIVE_MIGRATIONS_ALLOWED is not true")
        if not request.maintenance_mode:
            blockers.append("ENGINE_MAINTENANCE_MODE is not true")
        if not request.confirmed_backup_id:
            blockers.append("ENGINE_CONFIRMED_BACKUP_ID is missing")
        if not request.actor_has_administer:
            blockers.append("actor lacks ADMINISTER_ENGINE")
        if request.confirm_phrase != REQUIRED_CONFIRM_PHRASE:
            blockers.append("confirm phrase does not match")
        return blockers
