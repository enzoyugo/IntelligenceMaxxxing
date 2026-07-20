"""Rebuildable Stage 3 epistemic projections (ledger → derived tables).

Live tables are replaced atomically inside one transaction after a full
event replay. Verify replays into memory only and never mutates live.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import MutableMapping
from datetime import datetime
from typing import Any, cast

from intelligence_maxxxing.application.errors import UnknownProjectionEventError
from intelligence_maxxxing.application.ports import (
    HealthSnapshotProviderPort,
    ProjectedBeliefSnapshot,
    ProjectedEvidenceSnapshot,
    ProjectedExperiment,
    ProjectedExperimentProgress,
    ProjectedHypothesis,
    ProjectedLearningRecord,
    ProjectionCheckpoint,
    UnitOfWorkPort,
)
from intelligence_maxxxing.application.use_cases.projections import RebuildResult, VerifyReport
from intelligence_maxxxing.domain.audit.models import AuditRecord, EngineEvent
from intelligence_maxxxing.domain.common.base import CANONICAL_SCHEMA_VERSION, utc_now
from intelligence_maxxxing.domain.common.identifiers import AUDIT_PREFIX, EVENT_PREFIX, new_id
from intelligence_maxxxing.domain.identity.system import (
    SYSTEM_ACTOR,
    SYSTEM_APPLICATION_ID,
    SYSTEM_OWNER_ID,
    SYSTEM_TENANT_ID,
)
from intelligence_maxxxing.domain_packs.life.eligibility import (
    ANALYSIS_METHOD,
    HYPOTHESIS_STATEMENT,
    RANDOM_SEED_POLICY,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
)

EPISTEMIC_PROJECTION = "epistemic_loop"
EPISTEMIC_PROJECTION_VERSION = "1.0"
PROTOCOL_VERSION = "1.0"
MINIMUM_GROUP_SIZE = 10

_HANDLED = frozenset(
    {
        "HypothesisProposed",
        "HypothesisActivated",
        "HypothesisRetired",
        "ExperimentRegistered",
        "ExperimentObservationWindowOpened",
        "EvidenceEvaluated",
        "BeliefCreated",
        "BeliefUpdated",
        "OutcomeEvaluated",
        "LearningRecorded",
        "ExperimentCompleted",
        "ExperimentExpiredInconclusive",
    }
)


class EpistemicProjectionRebuildService:
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
        if not from_scratch:
            # Epistemic projections are rebuilt from zero (no incremental resume yet).
            return self.rebuild(from_scratch=True)
        with self._uow as uow:
            events = list(uow.events.stream_from_position(0, limit=1_000_000))
            state = _EpistemicState()
            last_position = 0
            last_event_id: str | None = None
            rows_written = 0
            try:
                for event in events:
                    applied = state.apply(event)
                    if applied:
                        rows_written += 1
                    if event.global_position is not None:
                        last_position = event.global_position
                    last_event_id = event.event_id
            except UnknownProjectionEventError:
                now = utc_now()
                uow.projections.save_checkpoint(
                    ProjectionCheckpoint(
                        projection_name=EPISTEMIC_PROJECTION,
                        projection_version=EPISTEMIC_PROJECTION_VERSION,
                        last_global_position=last_position,
                        last_event_id=last_event_id,
                        updated_at=now,
                        status="QUARANTINED",
                        checksum=None,
                    )
                )
                uow.commit()
                raise

            uow.epistemic.delete_all_epistemic_projections()
            state.write(uow)
            checksum = state.checksum()
            now = utc_now()
            uow.projections.save_checkpoint(
                ProjectionCheckpoint(
                    projection_name=EPISTEMIC_PROJECTION,
                    projection_version=EPISTEMIC_PROJECTION_VERSION,
                    last_global_position=last_position,
                    last_event_id=last_event_id,
                    updated_at=now,
                    status="READY",
                    checksum=checksum,
                )
            )
            audit_id = new_id(AUDIT_PREFIX)
            rebuilt = EngineEvent(
                event_id=new_id(EVENT_PREFIX),
                event_type="ProjectionRebuilt",
                aggregate_type="Projection",
                aggregate_id=EPISTEMIC_PROJECTION,
                aggregate_version=_next_projection_version(uow),
                domain_pack="core",
                tenant_id=SYSTEM_TENANT_ID,
                owner_id=SYSTEM_OWNER_ID,
                application_id=SYSTEM_APPLICATION_ID,
                actor=SYSTEM_ACTOR,
                schema_version=CANONICAL_SCHEMA_VERSION,
                payload={
                    "projection_name": EPISTEMIC_PROJECTION,
                    "projection_version": EPISTEMIC_PROJECTION_VERSION,
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
            uow.events.append_one(rebuilt)
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
                    action="projections.rebuild_epistemic",
                    input_object_ids=(),
                    output_object_ids=(EPISTEMIC_PROJECTION,),
                    event_ids=(rebuilt.event_id,),
                    timestamp=now,
                    health_state=snapshot.model_dump(mode="json"),
                )
            )
            uow.commit()

        return RebuildResult(
            projection_name=EPISTEMIC_PROJECTION,
            projection_version=EPISTEMIC_PROJECTION_VERSION,
            events_scanned=len(events),
            rows_written=rows_written,
            last_global_position=last_position,
            checksum=checksum,
            from_scratch=True,
        )

    def verify(self) -> VerifyReport:
        with self._uow as uow:
            live_checksum = _live_checksum(uow)
            live_rows = _live_row_count(uow)
            events = list(uow.events.stream_from_position(0, limit=1_000_000))
            state = _EpistemicState()
            quarantined = False
            try:
                for event in events:
                    state.apply(event)
            except UnknownProjectionEventError:
                quarantined = True
            shadow_checksum = state.checksum()
            shadow_rows = state.row_count()
            uow.commit()

        matches = (not quarantined) and shadow_checksum == live_checksum
        return VerifyReport(
            projection_name=EPISTEMIC_PROJECTION,
            projection_version=EPISTEMIC_PROJECTION_VERSION,
            ok=matches,
            matches=matches,
            quarantined=quarantined,
            live_rows=live_rows,
            shadow_rows=shadow_rows,
            live_checksum=live_checksum,
            shadow_checksum=shadow_checksum,
            events_scanned=len(events),
        )


class _EpistemicState:
    """In-memory epistemic projection used for rebuild + verify."""

    def __init__(self) -> None:
        self.hypotheses: MutableMapping[str, ProjectedHypothesis] = {}
        self.experiments: MutableMapping[str, ProjectedExperiment] = {}
        self.beliefs: MutableMapping[str, ProjectedBeliefSnapshot] = {}
        self.evidence: MutableMapping[str, ProjectedEvidenceSnapshot] = {}
        self.progress: MutableMapping[str, ProjectedExperimentProgress] = {}
        self.learning: MutableMapping[str, ProjectedLearningRecord] = {}

    def apply(self, event: EngineEvent) -> bool:
        if event.event_type in {
            "ObservationAccepted",
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
            "IntegrityStreamQuarantined",
            "IntegrityStreamVerified",
            "IntegrityStreamReleased",
        }:
            return False
        if event.event_type not in _HANDLED:
            raise UnknownProjectionEventError(
                f"unknown event type for epistemic projection: {event.event_type}"
            )
        if event.global_position is None:
            raise UnknownProjectionEventError(
                f"event {event.event_id} has no global_position; cannot project"
            )
        handler = getattr(self, f"_on_{event.event_type}")
        handler(event)
        return True

    def write(self, uow: UnitOfWorkPort) -> None:
        for hyp in self.hypotheses.values():
            uow.epistemic.upsert_hypothesis(hyp)
        for exp in self.experiments.values():
            uow.epistemic.upsert_experiment(exp)
        for evi in self.evidence.values():
            uow.epistemic.upsert_evidence_snapshot(evi)
        # Beliefs: write oldest first so is_current flips correctly.
        for bel in sorted(self.beliefs.values(), key=lambda r: r.global_position):
            uow.epistemic.upsert_belief_snapshot(bel)
        for prog in self.progress.values():
            uow.epistemic.upsert_experiment_progress(prog)
        for learn in self.learning.values():
            uow.epistemic.append_learning_record(learn)

    def row_count(self) -> int:
        return (
            len(self.hypotheses)
            + len(self.experiments)
            + len(self.beliefs)
            + len(self.evidence)
            + len(self.progress)
            + len(self.learning)
        )

    def checksum(self) -> str:
        material = {
            "hypotheses": [
                r.model_dump(mode="json")
                for r in sorted(self.hypotheses.values(), key=lambda x: x.hypothesis_id)
            ],
            "experiments": [
                r.model_dump(mode="json")
                for r in sorted(self.experiments.values(), key=lambda x: x.experiment_id)
            ],
            "beliefs": [
                r.model_dump(mode="json")
                for r in sorted(self.beliefs.values(), key=lambda x: x.belief_id)
            ],
            "evidence": [
                r.model_dump(mode="json")
                for r in sorted(self.evidence.values(), key=lambda x: x.evidence_id)
            ],
            "progress": [
                r.model_dump(mode="json")
                for r in sorted(self.progress.values(), key=lambda x: x.experiment_id)
            ],
            "learning": [
                r.model_dump(mode="json")
                for r in sorted(self.learning.values(), key=lambda x: x.learning_id)
            ],
        }
        canonical = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _on_HypothesisProposed(self, event: EngineEvent) -> None:
        p = cast(dict[str, Any], event.payload)
        now = event.occurred_at
        assert event.global_position is not None
        self.hypotheses[str(p["hypothesis_id"])] = ProjectedHypothesis(
            hypothesis_id=str(p["hypothesis_id"]),
            tenant_id=event.tenant_id,
            owner_id=event.owner_id,
            application_id=event.application_id,
            domain_pack=event.domain_pack,
            template_id=str(p.get("template_id", TEMPLATE_ID)),
            template_version=str(p.get("template_version", TEMPLATE_VERSION)),
            statement=str(p.get("statement", HYPOTHESIS_STATEMENT)),
            direction=str(p.get("direction", "POSITIVE")),
            causality_level=str(p.get("causality_level", "CORRELATION")),
            status="PROPOSED",
            human_confirmed=bool(p.get("human_confirmed", False)),
            parameters=(lambda d: d or None)(_as_obj_dict(p.get("parameters"))),
            proposed_at=now,
            audit_id=event.audit_id,
            event_id=event.event_id,
            global_position=event.global_position,
            updated_at=now,
        )

    def _on_HypothesisActivated(self, event: EngineEvent) -> None:
        p = cast(dict[str, Any], event.payload)
        hid = str(p["hypothesis_id"])
        existing = self.hypotheses.get(hid)
        if existing is None:
            return
        assert event.global_position is not None
        self.hypotheses[hid] = existing.model_copy(
            update={
                "status": "ACTIVE",
                "human_confirmed": True,
                "parameters": _as_obj_dict(p.get("parameters")) or existing.parameters,
                "activated_at": event.occurred_at,
                "experiment_id": str(p["experiment_id"]),
                "audit_id": event.audit_id,
                "event_id": event.event_id,
                "global_position": event.global_position,
                "updated_at": event.occurred_at,
            }
        )

    def _on_HypothesisRetired(self, event: EngineEvent) -> None:
        p = cast(dict[str, Any], event.payload)
        hid = str(p["hypothesis_id"])
        existing = self.hypotheses.get(hid)
        if existing is None:
            return
        assert event.global_position is not None
        self.hypotheses[hid] = existing.model_copy(
            update={
                "status": "RETIRED",
                "retired_at": event.occurred_at,
                "audit_id": event.audit_id,
                "event_id": event.event_id,
                "global_position": event.global_position,
                "updated_at": event.occurred_at,
            }
        )

    def _on_ExperimentRegistered(self, event: EngineEvent) -> None:
        p = cast(dict[str, Any], event.payload)
        assert event.global_position is not None
        eid = str(p["experiment_id"])
        hid = str(p["hypothesis_id"])
        params = _as_obj_dict(p)
        self.experiments[eid] = ProjectedExperiment(
            experiment_id=eid,
            tenant_id=event.tenant_id,
            owner_id=event.owner_id,
            application_id=event.application_id,
            hypothesis_id=hid,
            protocol_version=str(p.get("protocol_version", PROTOCOL_VERSION)),
            analysis_method=str(p.get("analysis_method", ANALYSIS_METHOD)),
            baseline_cutoff=_parse_dt(p["baseline_cutoff"], event.occurred_at),
            prospective_start=_parse_dt(p["prospective_start"], event.occurred_at),
            prospective_target=int(p["prospective_target"]),
            maximum_window_days=int(p["maximum_window_days"]),
            minimum_group_size=int(p.get("minimum_group_size", MINIMUM_GROUP_SIZE)),
            minimum_meaningful_difference=float(p["minimum_meaningful_difference"]),
            sleep_threshold_hours=float(p["sleep_threshold_hours"]),
            random_seed_policy=str(p.get("random_seed_policy", RANDOM_SEED_POLICY)),
            status="REGISTERED",
            pre_registered_at=event.occurred_at,
            audit_id=event.audit_id,
            event_id=event.event_id,
            global_position=event.global_position,
            updated_at=event.occurred_at,
            # Activation anchors are frozen on live activate; rebuild falls back
            # to the ExperimentRegistered position/time until HypothesisActivated
            # linkage is reconstructed.
            activation_event_id=event.event_id,
            activation_global_position=event.global_position,
            activation_recorded_at=event.occurred_at,
        )
        self.progress[eid] = ProjectedExperimentProgress(
            experiment_id=eid,
            hypothesis_id=hid,
            tenant_id=event.tenant_id,
            owner_id=event.owner_id,
            application_id=event.application_id,
            prospective_target=int(p["prospective_target"]),
            window_days_remaining=int(p["maximum_window_days"]),
            status="REGISTERED",
            updated_at=event.occurred_at,
        )
        _ = params

    def _on_ExperimentObservationWindowOpened(self, event: EngineEvent) -> None:
        p = cast(dict[str, Any], event.payload)
        eid = str(p["experiment_id"])
        progress = self.progress.get(eid)
        experiment = self.experiments.get(eid)
        if progress is not None:
            self.progress[eid] = progress.model_copy(
                update={"status": "IN_PROGRESS", "updated_at": event.occurred_at}
            )
        if experiment is not None:
            self.experiments[eid] = experiment.model_copy(
                update={"status": "IN_PROGRESS", "updated_at": event.occurred_at}
            )

    def _on_EvidenceEvaluated(self, event: EngineEvent) -> None:
        p = cast(dict[str, Any], event.payload)
        assert event.global_position is not None
        evidence_id = str(p["evidence_id"])
        eid = str(p["experiment_id"])
        phase = str(p["phase"])
        group_counts = {
            str(k): int(cast(Any, v)) for k, v in _as_obj_dict(p.get("group_counts")).items()
        }
        self.evidence[evidence_id] = ProjectedEvidenceSnapshot(
            evidence_id=evidence_id,
            tenant_id=event.tenant_id,
            owner_id=event.owner_id,
            application_id=event.application_id,
            hypothesis_id=str(p["hypothesis_id"]),
            experiment_id=eid,
            phase=phase,
            source_observation_ids=tuple(str(x) for x in (p.get("source_observation_ids") or ())),
            source_event_ids=tuple(str(x) for x in (p.get("source_event_ids") or ())),
            source_hash=str(p["source_hash"]),
            eligible_count=int(p["eligible_count"]),
            excluded_count=int(p["excluded_count"]),
            exclusion_reasons={
                str(k): int(cast(Any, v))
                for k, v in _as_obj_dict(p.get("exclusion_reasons")).items()
            },
            group_counts=group_counts,
            descriptive_statistics=_as_obj_dict(p.get("descriptive_statistics")),
            analysis_parameters=_as_obj_dict(p.get("analysis_parameters")),
            analysis_result=_as_obj_dict(p.get("analysis_result")) or None,
            confounding_diagnostics=tuple(
                _as_obj_dict(item) for item in (p.get("confounding_diagnostics") or ())
            ),
            limitations=tuple(str(x) for x in (p.get("limitations") or ())),
            belief_state=str(p["belief_state"]),
            generated_at=event.occurred_at,
            audit_id=event.audit_id,
            event_id=event.event_id,
            global_position=event.global_position,
        )
        progress = self.progress.get(eid)
        if progress is not None:
            updates: dict[str, Any] = {
                "current_belief_state": str(p["belief_state"]),
                "last_evaluated_at": event.occurred_at,
                "updated_at": event.occurred_at,
                "status": "IN_PROGRESS",
            }
            n_suf = group_counts.get("SUFFICIENT", 0)
            n_below = group_counts.get("BELOW_THRESHOLD", 0)
            eligible = int(p["eligible_count"])
            if phase == "BASELINE_EXPLORATORY":
                updates.update(
                    {
                        "baseline_eligible": eligible,
                        "baseline_sufficient": n_suf,
                        "baseline_below": n_below,
                    }
                )
            else:
                updates.update(
                    {
                        "prospective_eligible": eligible,
                        "prospective_sufficient": n_suf,
                        "prospective_below": n_below,
                    }
                )
            self.progress[eid] = progress.model_copy(update=updates)

    def _on_BeliefCreated(self, event: EngineEvent) -> None:
        self._upsert_belief(event, previous_optional=True)

    def _on_BeliefUpdated(self, event: EngineEvent) -> None:
        self._upsert_belief(event, previous_optional=False)

    def _upsert_belief(self, event: EngineEvent, *, previous_optional: bool) -> None:
        p = cast(dict[str, Any], event.payload)
        assert event.global_position is not None
        belief_id = str(p["belief_id"])
        hypothesis_id = str(p["hypothesis_id"])
        for existing_id, existing in list(self.beliefs.items()):
            if existing.hypothesis_id == hypothesis_id and existing.is_current:
                self.beliefs[existing_id] = existing.model_copy(update={"is_current": False})
        previous = p.get("previous_belief_id")
        self.beliefs[belief_id] = ProjectedBeliefSnapshot(
            belief_id=belief_id,
            tenant_id=event.tenant_id,
            owner_id=event.owner_id,
            application_id=event.application_id,
            hypothesis_id=hypothesis_id,
            evidence_id=str(p["evidence_id"]),
            previous_belief_id=None if previous is None else str(previous),
            belief_state=str(p["belief_state"]),
            model_probability=float(cast(Any, p["model_probability"])),
            credible_interval_low=float(cast(Any, p.get("credible_interval_low", 0.0))),
            credible_interval_high=float(cast(Any, p.get("credible_interval_high", 0.0))),
            estimated_effect=float(cast(Any, p["estimated_effect"])),
            minimum_meaningful_difference=float(
                cast(Any, p.get("minimum_meaningful_difference", 0.0))
            ),
            data_confidence=str(p.get("data_confidence", "LOW")),
            method_confidence=str(p.get("method_confidence", "MODERATE")),
            conclusion_confidence=str(p.get("conclusion_confidence", "LOW")),
            recommendation_confidence=str(p.get("recommendation_confidence", "VERY_LOW")),
            calibration_state=str(p["calibration_state"]),
            causality_level=str(p["causality_level"]),
            limitations=tuple(str(x) for x in cast(Any, p.get("limitations") or ())),
            is_current=True,
            created_at=event.occurred_at,
            audit_id=event.audit_id,
            event_id=event.event_id,
            global_position=event.global_position,
        )
        _ = previous_optional

    def _on_OutcomeEvaluated(self, event: EngineEvent) -> None:
        # Outcome evaluations are ledger-recorded; no dedicated live projection table.
        return

    def _on_LearningRecorded(self, event: EngineEvent) -> None:
        p = cast(dict[str, Any], event.payload)
        assert event.global_position is not None
        lid = str(p["learning_id"])
        self.learning[lid] = ProjectedLearningRecord(
            learning_id=lid,
            tenant_id=event.tenant_id,
            owner_id=event.owner_id,
            application_id=event.application_id,
            hypothesis_id=str(p["hypothesis_id"]),
            previous_belief_id=(
                None if p.get("previous_belief_id") is None else str(p["previous_belief_id"])
            ),
            new_belief_id=str(p["new_belief_id"]),
            outcome_evaluation_id=str(p["outcome_evaluation_id"]),
            change_type=str(p["change_type"]),
            what_changed=str(p["what_changed"]),
            why_changed=str(p["why_changed"]),
            what_remains_unknown=str(p["what_remains_unknown"]),
            next_evidence_needed=str(p["next_evidence_needed"]),
            created_at=event.occurred_at,
            audit_id=event.audit_id,
            event_id=event.event_id,
            global_position=event.global_position,
        )

    def _on_ExperimentCompleted(self, event: EngineEvent) -> None:
        p = cast(dict[str, Any], event.payload)
        eid = str(p["experiment_id"])
        experiment = self.experiments.get(eid)
        progress = self.progress.get(eid)
        if experiment is not None:
            self.experiments[eid] = experiment.model_copy(
                update={"status": "COMPLETED", "updated_at": event.occurred_at}
            )
        if progress is not None:
            self.progress[eid] = progress.model_copy(
                update={
                    "status": "COMPLETED",
                    "current_belief_state": str(p.get("final_belief_state")),
                    "updated_at": event.occurred_at,
                }
            )

    def _on_ExperimentExpiredInconclusive(self, event: EngineEvent) -> None:
        p = cast(dict[str, Any], event.payload)
        eid = str(p["experiment_id"])
        experiment = self.experiments.get(eid)
        progress = self.progress.get(eid)
        if experiment is not None:
            self.experiments[eid] = experiment.model_copy(
                update={"status": "EXPIRED", "updated_at": event.occurred_at}
            )
        if progress is not None:
            self.progress[eid] = progress.model_copy(
                update={"status": "EXPIRED", "updated_at": event.occurred_at}
            )


def _as_obj_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items()}
    return {}


def _parse_dt(value: object, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return fallback


def _next_projection_version(uow: UnitOfWorkPort) -> int:
    latest = uow.events.get_latest_aggregate_version(
        SYSTEM_TENANT_ID,
        SYSTEM_OWNER_ID,
        SYSTEM_APPLICATION_ID,
        "Projection",
        EPISTEMIC_PROJECTION,
    )
    return (latest or 0) + 1


def _live_row_count(uow: UnitOfWorkPort) -> int:
    return (
        len(uow.epistemic.list_all_hypotheses())
        + len(uow.epistemic.list_all_experiments())
        + len(uow.epistemic.list_all_belief_snapshots())
        + len(uow.epistemic.list_all_evidence_snapshots())
        + len(uow.epistemic.list_all_experiment_progress())
        + len(uow.epistemic.list_all_learning_records())
    )


def _live_checksum(uow: UnitOfWorkPort) -> str:
    state = _EpistemicState()
    for hyp in uow.epistemic.list_all_hypotheses():
        state.hypotheses[hyp.hypothesis_id] = hyp
    for exp in uow.epistemic.list_all_experiments():
        state.experiments[exp.experiment_id] = exp
    for bel in uow.epistemic.list_all_belief_snapshots():
        state.beliefs[bel.belief_id] = bel
    for evi in uow.epistemic.list_all_evidence_snapshots():
        state.evidence[evi.evidence_id] = evi
    for prog in uow.epistemic.list_all_experiment_progress():
        state.progress[prog.experiment_id] = prog
    for learn in uow.epistemic.list_all_learning_records():
        state.learning[learn.learning_id] = learn
    return state.checksum()
