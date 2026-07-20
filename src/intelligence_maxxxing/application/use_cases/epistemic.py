"""Stage 3 first epistemic loop use cases (hypothesis → experiment → evaluate).

Belief snapshots are produced only through governed evaluation; applications
never write beliefs directly. All writes follow submit_observation patterns:
AuthContext, UoW, catalog events, audits, idempotency.
"""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from intelligence_maxxxing.application.auth.service import AuthContext
from intelligence_maxxxing.application.errors import (
    ExperimentNotFoundError,
    HypothesisNotFoundError,
    HypothesisStateError,
    IdempotencyConflictError,
    IdempotencyRaceDetected,
)
from intelligence_maxxxing.application.ports import (
    HealthSnapshotProviderPort,
    IdempotencyRecord,
    ProjectedBeliefSnapshot,
    ProjectedEvidenceSnapshot,
    ProjectedExperiment,
    ProjectedExperimentProgress,
    ProjectedHypothesis,
    ProjectedLearningRecord,
    UnitOfWorkPort,
)
from intelligence_maxxxing.application.ports.clock import ClockPort
from intelligence_maxxxing.domain.audit.models import AuditRecord, EngineEvent
from intelligence_maxxxing.domain.common.base import CANONICAL_SCHEMA_VERSION, utc_now
from intelligence_maxxxing.domain.common.epistemic import (
    BeliefState,
    CalibrationState,
    CausalityLevel,
    ConfidenceLevel,
    EvaluationKind,
    EvidencePhase,
    HypothesisStatus,
    TerminalReason,
)
from intelligence_maxxxing.infrastructure.clock.system_clock import SystemClock
from intelligence_maxxxing.domain.common.identifiers import (
    AUDIT_PREFIX,
    BELIEF_PREFIX,
    EVENT_PREFIX,
    EVIDENCE_PREFIX,
    EXPERIMENT_PREFIX,
    HYPOTHESIS_PREFIX,
    LEARNING_PREFIX,
    OUTCOME_PREFIX,
    new_id,
)
from intelligence_maxxxing.domain.hypotheses.models import HypothesisParameters
from intelligence_maxxxing.domain_packs.life.eligibility import (
    ANALYSIS_METHOD,
    HYPOTHESIS_STATEMENT,
    OBSERVATIONAL_LIMITATION,
    RANDOM_SEED_POLICY,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    confounding_diagnostics,
    partition_exposure,
    select_eligible_checkins,
    split_by_temporal_anchors,
)
from intelligence_maxxxing.domain_packs.life.evidence_fingerprint import (
    compute_evidence_fingerprint,
    compute_source_hash,
    source_position_stats,
)
from intelligence_maxxxing.domain_packs.life.observation_scan import scan_all_life_observations
from intelligence_maxxxing.domain_packs.life.learning_templates import (
    agreement_with_prior,
    learning_texts,
)
from intelligence_maxxxing.domain_packs.life.methods.bayesian_bootstrap import (
    bayesian_bootstrap_difference_in_means,
    classify_belief_state,
    derive_seed,
)

HYPOTHESIS_AGGREGATE = "Hypothesis"
EXPERIMENT_AGGREGATE = "Experiment"
EVIDENCE_AGGREGATE = "Evidence"
BELIEF_AGGREGATE = "Belief"
OUTCOME_AGGREGATE = "Outcome"
LEARNING_AGGREGATE = "Learning"

PROPOSE_HYPOTHESIS_ACTION = "hypotheses.propose"
ACTIVATE_HYPOTHESIS_ACTION = "hypotheses.activate"
RETIRE_HYPOTHESIS_ACTION = "hypotheses.retire"
EVALUATE_EXPERIMENT_ACTION = "experiments.evaluate"

LIFE_DOMAIN_PACK = "life"
PROTOCOL_VERSION = "1.0"
MINIMUM_GROUP_SIZE = 7


def _payload_hash(model: BaseModel) -> str:
    material = model.model_dump(mode="json", exclude={"idempotency_key", "request_id"})
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _source_hash(observation_ids: tuple[str, ...]) -> str:
    canonical = json.dumps(sorted(observation_ids), separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _next_version(
    uow: UnitOfWorkPort,
    auth: AuthContext,
    aggregate_type: str,
    aggregate_id: str,
) -> int:
    latest = uow.events.get_latest_aggregate_version(
        auth.tenant_id,
        auth.owner_id,
        auth.application_id,
        aggregate_type,
        aggregate_id,
    )
    return 1 if latest is None else latest + 1


def _append_event(
    uow: UnitOfWorkPort,
    *,
    auth: AuthContext,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    aggregate_version: int,
    payload: dict[str, object],
    audit_id: str,
    request_id: str,
    idempotency_key: str | None,
    occurred_at: Any,
) -> EngineEvent:
    event = EngineEvent(
        event_id=new_id(EVENT_PREFIX),
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        aggregate_version=aggregate_version,
        domain_pack=LIFE_DOMAIN_PACK,
        tenant_id=auth.tenant_id,
        owner_id=auth.owner_id,
        application_id=auth.application_id,
        actor=auth.actor,
        schema_version=CANONICAL_SCHEMA_VERSION,
        payload=payload,
        occurred_at=occurred_at,
        recorded_at=utc_now(),
        audit_id=audit_id,
        request_id=request_id,
        idempotency_key=idempotency_key,
    )
    return uow.events.append_one(event)


def _append_audit(
    uow: UnitOfWorkPort,
    *,
    auth: AuthContext,
    audit_id: str,
    request_id: str,
    action: str,
    engine_version: str,
    api_version: str,
    health_provider: HealthSnapshotProviderPort,
    input_ids: tuple[str, ...] = (),
    output_ids: tuple[str, ...] = (),
    event_ids: tuple[str, ...] = (),
) -> None:
    snapshot = health_provider.capture()
    uow.audits.append(
        AuditRecord(
            audit_id=audit_id,
            request_id=request_id,
            engine_version=engine_version,
            api_version=api_version,
            schema_version=CANONICAL_SCHEMA_VERSION,
            domain_pack=LIFE_DOMAIN_PACK,
            tenant_id=auth.tenant_id,
            owner_id=auth.owner_id,
            application_id=auth.application_id,
            actor=auth.actor,
            action=action,
            input_object_ids=input_ids,
            output_object_ids=output_ids,
            event_ids=event_ids,
            timestamp=utc_now(),
            health_state=snapshot.model_dump(mode="json"),
        )
    )


def _data_confidence(total_n: int) -> ConfidenceLevel:
    if total_n < 14:
        return ConfidenceLevel.LOW
    if total_n < 30:
        return ConfidenceLevel.MODERATE
    return ConfidenceLevel.HIGH


def _conclusion_confidence(state: BeliefState) -> ConfidenceLevel:
    if state is BeliefState.INSUFFICIENT_EVIDENCE:
        return ConfidenceLevel.VERY_LOW
    if state in {
        BeliefState.EXPLORATORY_INCONCLUSIVE,
        BeliefState.PROSPECTIVE_INCONCLUSIVE,
        BeliefState.EXPIRED_INCONCLUSIVE,
    }:
        return ConfidenceLevel.LOW
    if state in {BeliefState.PROSPECTIVE_SUPPORTED, BeliefState.PROSPECTIVE_WEAKENED}:
        return ConfidenceLevel.MODERATE
    return ConfidenceLevel.LOW


class IdempotentWriteMixin:
    """Shared idempotency lookup/replay for epistemic write use cases."""

    _uow: UnitOfWorkPort
    _action: str
    _result_factory: Any

    def _find_existing(
        self,
        command: BaseModel,
        auth: AuthContext,
        payload_hash: str,
        idempotency_key: str,
    ) -> Any:
        with self._uow as uow:
            existing = uow.idempotency.get(
                application_id=auth.application_id,
                owner_id=auth.owner_id,
                action=self._action,
                idempotency_key=idempotency_key,
            )
            uow.commit()
        if existing is None:
            return None
        if existing.payload_hash != payload_hash:
            raise IdempotencyConflictError(
                "idempotency key was already used with a different payload"
            )
        if self._result_factory is not None:
            return self._result_factory(existing)
        return self._replay_from_record(existing, command, auth)

    def _replay_from_record(
        self, record: IdempotencyRecord, command: BaseModel, auth: AuthContext
    ) -> Any:
        raise NotImplementedError

    def _resolve_race(
        self,
        command: BaseModel,
        auth: AuthContext,
        payload_hash: str,
        idempotency_key: str,
    ) -> Any:
        replayed = self._find_existing(command, auth, payload_hash, idempotency_key)
        if replayed is None:
            raise IdempotencyConflictError(
                "idempotency race detected but winning record not readable"
            ) from None
        return replayed

    def _store_idempotency(
        self,
        uow: UnitOfWorkPort,
        auth: AuthContext,
        idempotency_key: str,
        payload_hash: str,
        primary_id: str,
        event_id: str,
        audit_id: str,
    ) -> None:
        uow.idempotency.put(
            IdempotencyRecord(
                tenant_id=auth.tenant_id,
                owner_id=auth.owner_id,
                application_id=auth.application_id,
                actor_id=auth.actor.actor_id,
                action=self._action,
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
                observation_id=primary_id,
                event_id=event_id,
                audit_id=audit_id,
            )
        )


class ProposeHypothesisCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    parameters: HypothesisParameters | None = None
    human_confirmed: bool = False
    idempotency_key: str = Field(min_length=1, max_length=256)
    request_id: str = Field(min_length=1)


class ProposeHypothesisResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    hypothesis_id: str
    event_id: str
    audit_id: str
    replayed: bool


class ProposeHypothesisUseCase(IdempotentWriteMixin):
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
        self._action = PROPOSE_HYPOTHESIS_ACTION
        self._result_factory = lambda r: ProposeHypothesisResult(
            hypothesis_id=r.observation_id,
            event_id=r.event_id,
            audit_id=r.audit_id,
            replayed=True,
        )

    def execute(
        self, command: ProposeHypothesisCommand, auth: AuthContext
    ) -> ProposeHypothesisResult:
        payload_hash = _payload_hash(command)
        replayed = self._find_existing(command, auth, payload_hash, command.idempotency_key)
        if replayed is not None:
            return cast(ProposeHypothesisResult, replayed)
        try:
            return self._write(command, auth, payload_hash)
        except IdempotencyRaceDetected:
            return cast(
                ProposeHypothesisResult,
                self._resolve_race(command, auth, payload_hash, command.idempotency_key),
            )

    def _write(
        self, command: ProposeHypothesisCommand, auth: AuthContext, payload_hash: str
    ) -> ProposeHypothesisResult:
        with self._uow as uow:
            now = utc_now()
            audit_id = new_id(AUDIT_PREFIX)
            hypothesis_id = new_id(HYPOTHESIS_PREFIX)
            params = None
            if command.parameters is not None:
                params = command.parameters.model_dump(mode="json")

            event = _append_event(
                uow,
                auth=auth,
                event_type="HypothesisProposed",
                aggregate_type=HYPOTHESIS_AGGREGATE,
                aggregate_id=hypothesis_id,
                aggregate_version=1,
                payload={
                    "hypothesis_id": hypothesis_id,
                    "template_id": TEMPLATE_ID,
                    "template_version": TEMPLATE_VERSION,
                    "statement": HYPOTHESIS_STATEMENT,
                    "direction": "POSITIVE",
                    "causality_level": CausalityLevel.CORRELATION.value,
                    "parameters": params,
                    "human_confirmed": command.human_confirmed,
                },
                audit_id=audit_id,
                request_id=command.request_id,
                idempotency_key=command.idempotency_key,
                occurred_at=now,
            )
            if event.global_position is None:
                raise RuntimeError("persisted event missing global_position")

            uow.epistemic.upsert_hypothesis(
                ProjectedHypothesis(
                    hypothesis_id=hypothesis_id,
                    tenant_id=auth.tenant_id,
                    owner_id=auth.owner_id,
                    application_id=auth.application_id,
                    domain_pack=LIFE_DOMAIN_PACK,
                    template_id=TEMPLATE_ID,
                    template_version=TEMPLATE_VERSION,
                    statement=HYPOTHESIS_STATEMENT,
                    direction="POSITIVE",
                    causality_level=CausalityLevel.CORRELATION.value,
                    status=HypothesisStatus.PROPOSED.value,
                    human_confirmed=command.human_confirmed,
                    parameters=params,
                    proposed_at=now,
                    activated_at=None,
                    retired_at=None,
                    experiment_id=None,
                    audit_id=audit_id,
                    event_id=event.event_id,
                    global_position=event.global_position,
                    updated_at=now,
                )
            )

            _append_audit(
                uow,
                auth=auth,
                audit_id=audit_id,
                request_id=command.request_id,
                action=PROPOSE_HYPOTHESIS_ACTION,
                engine_version=self._engine_version,
                api_version=self._api_version,
                health_provider=self._health,
                output_ids=(hypothesis_id,),
                event_ids=(event.event_id,),
            )
            self._store_idempotency(
                uow,
                auth,
                command.idempotency_key,
                payload_hash,
                hypothesis_id,
                event.event_id,
                audit_id,
            )
            uow.commit()

        return ProposeHypothesisResult(
            hypothesis_id=hypothesis_id,
            event_id=event.event_id,
            audit_id=audit_id,
            replayed=False,
        )


class ActivateHypothesisCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    hypothesis_id: str = Field(min_length=1)
    parameters: HypothesisParameters
    idempotency_key: str = Field(min_length=1, max_length=256)
    request_id: str = Field(min_length=1)


class ActivateHypothesisResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    hypothesis_id: str
    experiment_id: str
    event_id: str
    audit_id: str
    replayed: bool


class ActivateHypothesisUseCase(IdempotentWriteMixin):
    def __init__(
        self,
        uow: UnitOfWorkPort,
        engine_version: str,
        api_version: str,
        health_provider: HealthSnapshotProviderPort,
        clock: ClockPort | None = None,
    ) -> None:
        self._uow = uow
        self._engine_version = engine_version
        self._api_version = api_version
        self._health = health_provider
        self._clock = clock or SystemClock()
        self._action = ACTIVATE_HYPOTHESIS_ACTION
        self._result_factory = None  # custom replay via hypothesis projection

    def execute(
        self, command: ActivateHypothesisCommand, auth: AuthContext
    ) -> ActivateHypothesisResult:
        payload_hash = _payload_hash(command)
        replayed = self._find_existing(command, auth, payload_hash, command.idempotency_key)
        if replayed is not None:
            return cast(ActivateHypothesisResult, replayed)
        try:
            return self._write(command, auth, payload_hash)
        except IdempotencyRaceDetected:
            return cast(
                ActivateHypothesisResult,
                self._resolve_race(command, auth, payload_hash, command.idempotency_key),
            )

    def _replay_from_record(
        self, record: IdempotencyRecord, command: BaseModel, auth: AuthContext
    ) -> ActivateHypothesisResult:
        with self._uow as uow:
            hypothesis = uow.epistemic.get_hypothesis(
                auth.owner_id, auth.application_id, record.observation_id
            )
            uow.commit()
        if hypothesis is None or hypothesis.experiment_id is None:
            raise IdempotencyConflictError(
                "idempotency record exists but activated hypothesis is not readable"
            )
        return ActivateHypothesisResult(
            hypothesis_id=record.observation_id,
            experiment_id=hypothesis.experiment_id,
            event_id=record.event_id,
            audit_id=record.audit_id,
            replayed=True,
        )

    def _write(
        self, command: ActivateHypothesisCommand, auth: AuthContext, payload_hash: str
    ) -> ActivateHypothesisResult:
        with self._uow as uow:
            hypothesis = uow.epistemic.get_hypothesis(
                auth.owner_id, auth.application_id, command.hypothesis_id
            )
            if hypothesis is None:
                raise HypothesisNotFoundError(f"hypothesis not found: {command.hypothesis_id}")
            if hypothesis.status != HypothesisStatus.PROPOSED.value:
                raise HypothesisStateError(
                    f"hypothesis {command.hypothesis_id} must be PROPOSED to activate"
                )

            now = self._clock.now()
            audit_id = new_id(AUDIT_PREFIX)
            experiment_id = new_id(EXPERIMENT_PREFIX)
            params = command.parameters.model_dump(mode="json")
            cutoff = now.isoformat()
            start = now.isoformat()

            hyp_version = _next_version(uow, auth, HYPOTHESIS_AGGREGATE, command.hypothesis_id)
            activated = _append_event(
                uow,
                auth=auth,
                event_type="HypothesisActivated",
                aggregate_type=HYPOTHESIS_AGGREGATE,
                aggregate_id=command.hypothesis_id,
                aggregate_version=hyp_version,
                payload={
                    "hypothesis_id": command.hypothesis_id,
                    "experiment_id": experiment_id,
                    "parameters": params,
                    "baseline_cutoff": cutoff,
                    "prospective_start": start,
                    "prospective_target": command.parameters.prospective_target,
                    "maximum_window_days": command.parameters.maximum_window_days,
                },
                audit_id=audit_id,
                request_id=command.request_id,
                idempotency_key=command.idempotency_key,
                occurred_at=now,
            )
            registered = _append_event(
                uow,
                auth=auth,
                event_type="ExperimentRegistered",
                aggregate_type=EXPERIMENT_AGGREGATE,
                aggregate_id=experiment_id,
                aggregate_version=1,
                payload={
                    "experiment_id": experiment_id,
                    "hypothesis_id": command.hypothesis_id,
                    "protocol_version": PROTOCOL_VERSION,
                    "analysis_method": ANALYSIS_METHOD,
                    "baseline_cutoff": cutoff,
                    "prospective_start": start,
                    "prospective_target": command.parameters.prospective_target,
                    "maximum_window_days": command.parameters.maximum_window_days,
                    "minimum_group_size": MINIMUM_GROUP_SIZE,
                    "minimum_meaningful_difference": (
                        command.parameters.minimum_meaningful_difference
                    ),
                    "sleep_threshold_hours": command.parameters.sleep_threshold_hours,
                    "random_seed_policy": RANDOM_SEED_POLICY,
                },
                audit_id=audit_id,
                request_id=command.request_id,
                idempotency_key=None,
                occurred_at=now,
            )
            if activated.global_position is None:
                raise RuntimeError("activation event missing global_position")
            window_opened = _append_event(
                uow,
                auth=auth,
                event_type="ExperimentObservationWindowOpened",
                aggregate_type=EXPERIMENT_AGGREGATE,
                aggregate_id=experiment_id,
                aggregate_version=2,
                payload={
                    "experiment_id": experiment_id,
                    "hypothesis_id": command.hypothesis_id,
                    "phase": EvidencePhase.BASELINE_EXPLORATORY.value,
                    "opened_at": start,
                },
                audit_id=audit_id,
                request_id=command.request_id,
                idempotency_key=None,
                occurred_at=now,
            )
            if registered.global_position is None:
                raise RuntimeError("persisted event missing global_position")

            uow.epistemic.upsert_hypothesis(
                ProjectedHypothesis(
                    hypothesis_id=hypothesis.hypothesis_id,
                    tenant_id=hypothesis.tenant_id,
                    owner_id=hypothesis.owner_id,
                    application_id=hypothesis.application_id,
                    domain_pack=hypothesis.domain_pack,
                    template_id=hypothesis.template_id,
                    template_version=hypothesis.template_version,
                    statement=hypothesis.statement,
                    direction=hypothesis.direction,
                    causality_level=hypothesis.causality_level,
                    status=HypothesisStatus.ACTIVE.value,
                    human_confirmed=True,
                    parameters=params,
                    proposed_at=hypothesis.proposed_at,
                    activated_at=now,
                    retired_at=None,
                    experiment_id=experiment_id,
                    audit_id=audit_id,
                    event_id=activated.event_id,
                    global_position=activated.global_position or hypothesis.global_position,
                    updated_at=now,
                )
            )
            uow.epistemic.upsert_experiment(
                ProjectedExperiment(
                    experiment_id=experiment_id,
                    tenant_id=auth.tenant_id,
                    owner_id=auth.owner_id,
                    application_id=auth.application_id,
                    hypothesis_id=command.hypothesis_id,
                    protocol_version=PROTOCOL_VERSION,
                    analysis_method=ANALYSIS_METHOD,
                    baseline_cutoff=now,
                    prospective_start=now,
                    prospective_target=command.parameters.prospective_target,
                    maximum_window_days=command.parameters.maximum_window_days,
                    minimum_group_size=MINIMUM_GROUP_SIZE,
                    minimum_meaningful_difference=command.parameters.minimum_meaningful_difference,
                    sleep_threshold_hours=command.parameters.sleep_threshold_hours,
                    random_seed_policy=RANDOM_SEED_POLICY,
                    status="REGISTERED",
                    pre_registered_at=now,
                    audit_id=audit_id,
                    event_id=registered.event_id,
                    global_position=registered.global_position,
                    updated_at=now,
                    activation_event_id=activated.event_id,
                    activation_global_position=activated.global_position,
                    activation_recorded_at=now,
                )
            )
            uow.epistemic.upsert_experiment_progress(
                ProjectedExperimentProgress(
                    experiment_id=experiment_id,
                    hypothesis_id=command.hypothesis_id,
                    tenant_id=auth.tenant_id,
                    owner_id=auth.owner_id,
                    application_id=auth.application_id,
                    prospective_target=command.parameters.prospective_target,
                    window_days_remaining=command.parameters.maximum_window_days,
                    status="COLLECTING_BASELINE",
                    updated_at=now,
                    target_remaining=command.parameters.prospective_target,
                    minimum_group_size=MINIMUM_GROUP_SIZE,
                    terminal=False,
                    terminal_reason=TerminalReason.NOT_TERMINAL.value,
                )
            )

            event_ids = (
                activated.event_id,
                registered.event_id,
                window_opened.event_id,
            )
            _append_audit(
                uow,
                auth=auth,
                audit_id=audit_id,
                request_id=command.request_id,
                action=ACTIVATE_HYPOTHESIS_ACTION,
                engine_version=self._engine_version,
                api_version=self._api_version,
                health_provider=self._health,
                input_ids=(command.hypothesis_id,),
                output_ids=(command.hypothesis_id, experiment_id),
                event_ids=event_ids,
            )
            self._store_idempotency(
                uow,
                auth,
                command.idempotency_key,
                payload_hash,
                command.hypothesis_id,
                activated.event_id,
                audit_id,
            )
            uow.commit()

        return ActivateHypothesisResult(
            hypothesis_id=command.hypothesis_id,
            experiment_id=experiment_id,
            event_id=activated.event_id,
            audit_id=audit_id,
            replayed=False,
        )


class RetireHypothesisCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    hypothesis_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1, max_length=256)
    request_id: str = Field(min_length=1)


class RetireHypothesisResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    hypothesis_id: str
    event_id: str
    audit_id: str
    replayed: bool


class RetireHypothesisUseCase(IdempotentWriteMixin):
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
        self._action = RETIRE_HYPOTHESIS_ACTION
        self._result_factory = lambda r: RetireHypothesisResult(
            hypothesis_id=r.observation_id,
            event_id=r.event_id,
            audit_id=r.audit_id,
            replayed=True,
        )

    def execute(
        self, command: RetireHypothesisCommand, auth: AuthContext
    ) -> RetireHypothesisResult:
        payload_hash = _payload_hash(command)
        replayed = self._find_existing(command, auth, payload_hash, command.idempotency_key)
        if replayed is not None:
            return cast(RetireHypothesisResult, replayed)
        try:
            return self._write(command, auth, payload_hash)
        except IdempotencyRaceDetected:
            return cast(
                RetireHypothesisResult,
                self._resolve_race(command, auth, payload_hash, command.idempotency_key),
            )

    def _write(
        self, command: RetireHypothesisCommand, auth: AuthContext, payload_hash: str
    ) -> RetireHypothesisResult:
        with self._uow as uow:
            hypothesis = uow.epistemic.get_hypothesis(
                auth.owner_id, auth.application_id, command.hypothesis_id
            )
            if hypothesis is None:
                raise HypothesisNotFoundError(f"hypothesis not found: {command.hypothesis_id}")
            if hypothesis.status == HypothesisStatus.RETIRED.value:
                raise HypothesisStateError(f"hypothesis {command.hypothesis_id} is already retired")

            now = utc_now()
            audit_id = new_id(AUDIT_PREFIX)
            version = _next_version(uow, auth, HYPOTHESIS_AGGREGATE, command.hypothesis_id)
            event = _append_event(
                uow,
                auth=auth,
                event_type="HypothesisRetired",
                aggregate_type=HYPOTHESIS_AGGREGATE,
                aggregate_id=command.hypothesis_id,
                aggregate_version=version,
                payload={
                    "hypothesis_id": command.hypothesis_id,
                    "reason": command.reason,
                    "previous_status": hypothesis.status,
                },
                audit_id=audit_id,
                request_id=command.request_id,
                idempotency_key=command.idempotency_key,
                occurred_at=now,
            )
            if event.global_position is None:
                raise RuntimeError("persisted event missing global_position")

            uow.epistemic.upsert_hypothesis(
                ProjectedHypothesis(
                    hypothesis_id=hypothesis.hypothesis_id,
                    tenant_id=hypothesis.tenant_id,
                    owner_id=hypothesis.owner_id,
                    application_id=hypothesis.application_id,
                    domain_pack=hypothesis.domain_pack,
                    template_id=hypothesis.template_id,
                    template_version=hypothesis.template_version,
                    statement=hypothesis.statement,
                    direction=hypothesis.direction,
                    causality_level=hypothesis.causality_level,
                    status=HypothesisStatus.RETIRED.value,
                    human_confirmed=hypothesis.human_confirmed,
                    parameters=hypothesis.parameters,
                    proposed_at=hypothesis.proposed_at,
                    activated_at=hypothesis.activated_at,
                    retired_at=now,
                    experiment_id=hypothesis.experiment_id,
                    audit_id=audit_id,
                    event_id=event.event_id,
                    global_position=event.global_position,
                    updated_at=now,
                )
            )

            _append_audit(
                uow,
                auth=auth,
                audit_id=audit_id,
                request_id=command.request_id,
                action=RETIRE_HYPOTHESIS_ACTION,
                engine_version=self._engine_version,
                api_version=self._api_version,
                health_provider=self._health,
                input_ids=(command.hypothesis_id,),
                output_ids=(command.hypothesis_id,),
                event_ids=(event.event_id,),
            )
            self._store_idempotency(
                uow,
                auth,
                command.idempotency_key,
                payload_hash,
                command.hypothesis_id,
                event.event_id,
                audit_id,
            )
            uow.commit()

        return RetireHypothesisResult(
            hypothesis_id=command.hypothesis_id,
            event_id=event.event_id,
            audit_id=audit_id,
            replayed=False,
        )


# EvaluateExperiment* lives in evaluate_experiment_v31 (Stage 3.1).
from intelligence_maxxxing.application.use_cases.evaluate_experiment_v31 import (  # noqa: E402
    EvaluateExperimentCommand,
    EvaluateExperimentResult,
    EvaluateExperimentUseCase,
)


class GetHypothesisUseCase:
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self._uow = uow

    def execute(self, hypothesis_id: str, auth: AuthContext) -> ProjectedHypothesis:
        with self._uow as uow:
            row = uow.epistemic.get_hypothesis(auth.owner_id, auth.application_id, hypothesis_id)
            uow.commit()
        if row is None:
            raise HypothesisNotFoundError(f"hypothesis not found: {hypothesis_id}")
        return row


class ListHypothesesUseCase:
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self._uow = uow

    def execute(self, auth: AuthContext, *, limit: int = 50) -> tuple[ProjectedHypothesis, ...]:
        with self._uow as uow:
            rows = uow.epistemic.list_hypotheses(auth.owner_id, auth.application_id, limit=limit)
            uow.commit()
        return tuple(rows)


class GetExperimentUseCase:
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self._uow = uow

    def execute(self, experiment_id: str, auth: AuthContext) -> ProjectedExperiment:
        with self._uow as uow:
            row = uow.epistemic.get_experiment(auth.owner_id, auth.application_id, experiment_id)
            uow.commit()
        if row is None:
            raise ExperimentNotFoundError(f"experiment not found: {experiment_id}")
        return row


class GetExperimentProgressUseCase:
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self._uow = uow

    def execute(self, experiment_id: str, auth: AuthContext) -> ProjectedExperimentProgress:
        with self._uow as uow:
            row = uow.epistemic.get_experiment_progress(
                auth.owner_id, auth.application_id, experiment_id
            )
            uow.commit()
        if row is None:
            raise ExperimentNotFoundError(f"experiment progress not found: {experiment_id}")
        return row


class GetCurrentBeliefUseCase:
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self._uow = uow

    def execute(self, hypothesis_id: str, auth: AuthContext) -> ProjectedBeliefSnapshot | None:
        with self._uow as uow:
            row = uow.epistemic.get_current_belief(
                auth.owner_id, auth.application_id, hypothesis_id
            )
            uow.commit()
        return row


class ListBeliefsUseCase:
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self._uow = uow

    def execute(self, hypothesis_id: str, auth: AuthContext) -> tuple[ProjectedBeliefSnapshot, ...]:
        with self._uow as uow:
            hypothesis = uow.epistemic.get_hypothesis(
                auth.owner_id, auth.application_id, hypothesis_id
            )
            if hypothesis is None:
                uow.commit()
                raise HypothesisNotFoundError(f"hypothesis not found: {hypothesis_id}")
            rows = uow.epistemic.list_belief_snapshots(
                auth.owner_id, auth.application_id, hypothesis_id
            )
            uow.commit()
        return tuple(rows)


class ListLearningUseCase:
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self._uow = uow

    def execute(self, hypothesis_id: str, auth: AuthContext) -> tuple[ProjectedLearningRecord, ...]:
        with self._uow as uow:
            hypothesis = uow.epistemic.get_hypothesis(
                auth.owner_id, auth.application_id, hypothesis_id
            )
            if hypothesis is None:
                uow.commit()
                raise HypothesisNotFoundError(f"hypothesis not found: {hypothesis_id}")
            rows = uow.epistemic.list_learning_records(
                auth.owner_id, auth.application_id, hypothesis_id
            )
            uow.commit()
        return tuple(rows)
