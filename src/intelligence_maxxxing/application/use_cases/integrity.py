"""Integrity chain verification and quarantine (Stage 1 §11 / Stage 1.1 §4-6).

Chain scope: per (tenant, owner, application) stream. Concurrency safety comes
from the transactional stream head (see the event store); this module verifies
that the recorded chain is intact and reacts to breaks.

Modes:
- FULL: verify a stream from its first event; on success advance its integrity
  checkpoint to the tip.
- INCREMENTAL: verify only the events after the stream's last trusted
  checkpoint, using the checkpoint hash as the anchor for the first event so a
  legitimate mid-stream start is never mistaken for corruption. Without a
  checkpoint it falls back to FULL for that stream.

On a detected break the stream is QUARANTINED (a real kill-switch): every new
append to it is rejected until an operator releases it through the governed
admin path (`unquarantine_stream`), which requires a successful full
verification. This is tamper/corruption DETECTION, not absolute cryptographic
security.
"""

from pydantic import BaseModel, ConfigDict

from intelligence_maxxxing.application.errors import (
    StreamNotFoundError,
    StreamReleaseBlockedError,
)
from intelligence_maxxxing.application.ports import (
    HealthSnapshotProviderPort,
    IntegrityStreamCheckpoint,
    IntegrityViolationHookPort,
    StreamHead,
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
from intelligence_maxxxing.permissions import PermissionScope


class StreamViolation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str
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


class StreamVerifyResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str
    owner_id: str
    application_id: str
    events_checked: int
    ok: bool
    broken_event_id: str | None = None


class _StreamOutcome:
    """Internal per-stream verification outcome before events are emitted."""

    def __init__(
        self,
        tenant_id: str,
        owner_id: str,
        application_id: str,
        events: list[EngineEvent],
        anchor: str | None,
        ok: bool,
        broken_event_id: str | None,
    ) -> None:
        self.tenant_id = tenant_id
        self.owner_id = owner_id
        self.application_id = application_id
        self.events = events
        self.anchor = anchor
        self.ok = ok
        self.broken_event_id = broken_event_id


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

    # --------------------------------------------------------------- verify all

    def verify(self, *, mode: str = "FULL") -> IntegrityReport:
        if mode not in {"FULL", "INCREMENTAL"}:
            raise ValueError("mode must be FULL or INCREMENTAL")

        with self._uow as uow:
            stream_keys = list(uow.events.list_stream_keys())
            outcomes: list[_StreamOutcome] = []
            events_checked = 0

            for tenant_id, owner_id, application_id in stream_keys:
                outcome = self._verify_stream(uow, tenant_id, owner_id, application_id, mode)
                events_checked += len(outcome.events)
                outcomes.append(outcome)

            now = utc_now()
            violations = tuple(
                StreamViolation(
                    tenant_id=o.tenant_id,
                    owner_id=o.owner_id,
                    application_id=o.application_id,
                    broken_event_id=o.broken_event_id,
                )
                for o in outcomes
                if not o.ok and o.broken_event_id is not None
            )

            # Advance checkpoints ONLY for streams that verified cleanly.
            for outcome in outcomes:
                if outcome.ok:
                    self._advance_checkpoint(uow, outcome)

            audit_id = new_id(AUDIT_PREFIX)
            completed = self._system_event(
                uow,
                event_type="IntegrityCheckCompleted",
                aggregate_type="IntegrityCheck",
                aggregate_id=f"integrity_{audit_id}",
                payload={
                    "streams_checked": len(stream_keys),
                    "events_checked": events_checked,
                    "violations_found": len(violations),
                    "mode": mode,
                    "completed_at": now.isoformat(),
                },
                audit_id=audit_id,
            )

            for violation in violations:
                self._quarantine(uow, violation, audit_id)

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
            violations=violations,
            ok=len(violations) == 0,
        )

    # ------------------------------------------------------ single-stream admin

    def inspect_stream(
        self, tenant_id: str, owner_id: str, application_id: str
    ) -> tuple[StreamHead | None, IntegrityStreamCheckpoint | None]:
        with self._uow as uow:
            head = uow.integrity.get_stream_head(tenant_id, owner_id, application_id)
            checkpoint = uow.integrity.get_integrity_checkpoint(tenant_id, owner_id, application_id)
            uow.commit()
        return head, checkpoint

    def verify_stream(
        self, tenant_id: str, owner_id: str, application_id: str
    ) -> StreamVerifyResult:
        """FULL verification of a single stream (read + record, no release)."""
        with self._uow as uow:
            head = uow.integrity.get_stream_head(tenant_id, owner_id, application_id)
            if head is None:
                raise StreamNotFoundError(
                    f"no stream head for ({tenant_id}, {owner_id}, {application_id})"
                )
            outcome = self._verify_stream(uow, tenant_id, owner_id, application_id, "FULL")
            now = utc_now()
            if outcome.ok:
                self._advance_checkpoint(uow, outcome)
                audit_id = new_id(AUDIT_PREFIX)
                self._system_event(
                    uow,
                    event_type="IntegrityStreamVerified",
                    aggregate_type="IntegrityStream",
                    aggregate_id=f"stream_{tenant_id}_{owner_id}_{application_id}",
                    payload={
                        "stream_tenant_id": tenant_id,
                        "stream_owner_id": owner_id,
                        "stream_application_id": application_id,
                        "events_checked": len(outcome.events),
                        "verified_at": now.isoformat(),
                    },
                    audit_id=audit_id,
                )
            uow.commit()
        return StreamVerifyResult(
            tenant_id=tenant_id,
            owner_id=owner_id,
            application_id=application_id,
            events_checked=len(outcome.events),
            ok=outcome.ok,
            broken_event_id=outcome.broken_event_id,
        )

    def unquarantine_stream(
        self,
        tenant_id: str,
        owner_id: str,
        application_id: str,
        *,
        reason: str,
        admin_actor_id: str,
        actor_scopes: frozenset[str],
    ) -> StreamVerifyResult:
        """Release a quarantined stream. Requires ADMINISTER_ENGINE and a
        successful FULL verification; records an append-only release event."""
        if PermissionScope.ADMINISTER_ENGINE.value not in actor_scopes:
            raise StreamReleaseBlockedError(
                "releasing a quarantined stream requires ADMINISTER_ENGINE"
            )
        with self._uow as uow:
            head = uow.integrity.get_stream_head(tenant_id, owner_id, application_id)
            if head is None:
                raise StreamNotFoundError(
                    f"no stream head for ({tenant_id}, {owner_id}, {application_id})"
                )
            outcome = self._verify_stream(uow, tenant_id, owner_id, application_id, "FULL")
            if not outcome.ok:
                raise StreamReleaseBlockedError(
                    "full verification still fails; stream cannot be released "
                    f"(first broken event: {outcome.broken_event_id})"
                )
            now = utc_now()
            self._advance_checkpoint(uow, outcome)
            uow.integrity.release_stream(tenant_id, owner_id, application_id)
            audit_id = new_id(AUDIT_PREFIX)
            event = self._system_event(
                uow,
                event_type="IntegrityStreamReleased",
                aggregate_type="IntegrityStream",
                aggregate_id=f"stream_{tenant_id}_{owner_id}_{application_id}",
                payload={
                    "stream_tenant_id": tenant_id,
                    "stream_owner_id": owner_id,
                    "stream_application_id": application_id,
                    "reason": reason,
                    "released_by": admin_actor_id,
                    "released_at": now.isoformat(),
                },
                audit_id=audit_id,
            )
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
                    action="integrity.unquarantine_stream",
                    input_object_ids=(application_id,),
                    output_object_ids=(),
                    event_ids=(event.event_id,),
                    timestamp=now,
                    health_state=snapshot.model_dump(mode="json"),
                )
            )
            uow.commit()
        return StreamVerifyResult(
            tenant_id=tenant_id,
            owner_id=owner_id,
            application_id=application_id,
            events_checked=len(outcome.events),
            ok=True,
        )

    # ------------------------------------------------------------------ helpers

    def _verify_stream(
        self,
        uow: UnitOfWorkPort,
        tenant_id: str,
        owner_id: str,
        application_id: str,
        mode: str,
    ) -> _StreamOutcome:
        anchor: str | None = None
        from_position = 0
        if mode == "INCREMENTAL":
            checkpoint = uow.integrity.get_integrity_checkpoint(tenant_id, owner_id, application_id)
            if checkpoint is not None:
                anchor = checkpoint.last_verified_hash
                from_position = checkpoint.last_verified_global_position
        events = list(
            uow.events.stream_for_stream_key(
                tenant_id, owner_id, application_id, from_position=from_position
            )
        )
        ok, broken = verify_chain(events, initial_previous_hash=anchor)
        return _StreamOutcome(tenant_id, owner_id, application_id, events, anchor, ok, broken)

    def _advance_checkpoint(self, uow: UnitOfWorkPort, outcome: _StreamOutcome) -> None:
        if not outcome.events:
            return
        last = outcome.events[-1]
        if last.global_position is None:
            return
        uow.integrity.save_integrity_checkpoint(
            IntegrityStreamCheckpoint(
                tenant_id=outcome.tenant_id,
                owner_id=outcome.owner_id,
                application_id=outcome.application_id,
                last_verified_global_position=last.global_position,
                last_verified_event_id=last.event_id,
                last_verified_hash=last.event_hash or outcome.anchor,
                verified_at=utc_now(),
                status="OK",
            )
        )

    def _quarantine(self, uow: UnitOfWorkPort, violation: StreamViolation, audit_id: str) -> None:
        self._hook.on_violation(
            violation.owner_id, violation.application_id, violation.broken_event_id
        )
        reason = "integrity chain break detected"
        uow.integrity.quarantine_stream(
            violation.tenant_id,
            violation.owner_id,
            violation.application_id,
            reason=reason,
            broken_event_id=violation.broken_event_id,
            audit_id=audit_id,
            detected_at=utc_now(),
        )
        self._system_event(
            uow,
            event_type="IntegrityViolationDetected",
            aggregate_type="IntegrityCheck",
            aggregate_id=f"integrity_violation_{violation.broken_event_id}",
            payload={
                "stream_owner_id": violation.owner_id,
                "stream_application_id": violation.application_id,
                "broken_event_id": violation.broken_event_id,
                "detected_at": utc_now().isoformat(),
            },
            audit_id=audit_id,
        )
        self._system_event(
            uow,
            event_type="IntegrityStreamQuarantined",
            aggregate_type="IntegrityStream",
            aggregate_id=(
                f"stream_{violation.tenant_id}_{violation.owner_id}_{violation.application_id}"
            ),
            payload={
                "stream_tenant_id": violation.tenant_id,
                "stream_owner_id": violation.owner_id,
                "stream_application_id": violation.application_id,
                "reason": reason,
                "broken_event_id": violation.broken_event_id,
                "detected_at": utc_now().isoformat(),
            },
            audit_id=audit_id,
        )

    def _system_event(
        self,
        uow: UnitOfWorkPort,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, object],
        audit_id: str,
    ) -> EngineEvent:
        moment = utc_now()
        latest = uow.events.get_latest_aggregate_version(
            SYSTEM_TENANT_ID,
            SYSTEM_OWNER_ID,
            SYSTEM_APPLICATION_ID,
            aggregate_type,
            aggregate_id,
        )
        event = EngineEvent(
            event_id=new_id(EVENT_PREFIX),
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            aggregate_version=(latest or 0) + 1,
            domain_pack="core",
            tenant_id=SYSTEM_TENANT_ID,
            owner_id=SYSTEM_OWNER_ID,
            application_id=SYSTEM_APPLICATION_ID,
            actor=SYSTEM_ACTOR,
            schema_version=CANONICAL_SCHEMA_VERSION,
            payload=payload,
            occurred_at=moment,
            recorded_at=moment,
            audit_id=audit_id,
            request_id=audit_id,
        )
        return uow.events.append_one(event)


class LoggingIntegrityViolationHook(IntegrityViolationHookPort):
    """Kill-switch side hook: structured error log. The authoritative
    kill-switch is the stream QUARANTINE performed by the verification service;
    this hook adds an operator-visible alert."""

    def on_violation(self, owner_id: str, application_id: str, broken_event_id: str) -> None:
        from intelligence_maxxxing.observability.logging import get_logger

        get_logger("intelligence_maxxxing.integrity").error(
            "integrity violation detected; stream will be quarantined",
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
