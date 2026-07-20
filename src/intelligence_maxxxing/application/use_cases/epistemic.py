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
    ObservationListFilters,
    ProjectedBeliefSnapshot,
    ProjectedEvidenceSnapshot,
    ProjectedExperiment,
    ProjectedExperimentProgress,
    ProjectedHypothesis,
    ProjectedLearningRecord,
    UnitOfWorkPort,
)
from intelligence_maxxxing.domain.audit.models import AuditRecord, EngineEvent
from intelligence_maxxxing.domain.common.base import CANONICAL_SCHEMA_VERSION, utc_now
from intelligence_maxxxing.domain.common.epistemic import (
    BeliefState,
    CalibrationState,
    CausalityLevel,
    ConfidenceLevel,
    EvidencePhase,
    HypothesisStatus,
)
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
    split_by_cutoff,
)
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
    ) -> None:
        self._uow = uow
        self._engine_version = engine_version
        self._api_version = api_version
        self._health = health_provider
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

            now = utc_now()
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
                    status="REGISTERED",
                    updated_at=now,
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


class EvaluateExperimentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_id: str = Field(min_length=1)
    phase: EvidencePhase
    idempotency_key: str = Field(min_length=1, max_length=256)
    request_id: str = Field(min_length=1)


class EvaluateExperimentResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_id: str
    evidence_id: str
    belief_id: str
    belief_state: str
    event_id: str
    audit_id: str
    replayed: bool


class EvaluateExperimentUseCase(IdempotentWriteMixin):
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
        self._action = EVALUATE_EXPERIMENT_ACTION
        self._result_factory = None

    def execute(
        self, command: EvaluateExperimentCommand, auth: AuthContext
    ) -> EvaluateExperimentResult:
        payload_hash = _payload_hash(command)
        replayed = self._find_existing(command, auth, payload_hash, command.idempotency_key)
        if replayed is not None:
            return cast(EvaluateExperimentResult, replayed)
        try:
            return self._write(command, auth, payload_hash)
        except IdempotencyRaceDetected:
            return cast(
                EvaluateExperimentResult,
                self._resolve_race(command, auth, payload_hash, command.idempotency_key),
            )

    def _replay_from_record(
        self, record: IdempotencyRecord, command: BaseModel, auth: AuthContext
    ) -> EvaluateExperimentResult:
        evaluate_command = command if isinstance(command, EvaluateExperimentCommand) else None
        experiment_id = (
            evaluate_command.experiment_id if evaluate_command else record.observation_id
        )
        with self._uow as uow:
            belief = uow.epistemic.get_belief_snapshot(
                auth.owner_id, auth.application_id, record.event_id
            )
            uow.commit()
        return EvaluateExperimentResult(
            experiment_id=experiment_id,
            evidence_id=record.observation_id,
            belief_id=record.event_id,
            belief_state=belief.belief_state if belief else "",
            event_id=record.event_id,
            audit_id=record.audit_id,
            replayed=True,
        )

    def _write(
        self, command: EvaluateExperimentCommand, auth: AuthContext, payload_hash: str
    ) -> EvaluateExperimentResult:
        with self._uow as uow:
            experiment = uow.epistemic.get_experiment(
                auth.owner_id, auth.application_id, command.experiment_id
            )
            if experiment is None:
                raise ExperimentNotFoundError(f"experiment not found: {command.experiment_id}")

            hypothesis = uow.epistemic.get_hypothesis(
                auth.owner_id, auth.application_id, experiment.hypothesis_id
            )
            if hypothesis is None:
                raise HypothesisNotFoundError(f"hypothesis not found: {experiment.hypothesis_id}")
            if hypothesis.status == HypothesisStatus.RETIRED.value:
                raise HypothesisStateError("cannot evaluate a retired hypothesis")

            now = utc_now()
            audit_id = new_id(AUDIT_PREFIX)
            evidence_id = new_id(EVIDENCE_PREFIX)
            belief_id = new_id(BELIEF_PREFIX)

            observations = uow.projections.list_observations(
                auth.owner_id,
                auth.application_id,
                ObservationListFilters(domain_pack=LIFE_DOMAIN_PACK, limit=500),
            )
            eligibility = select_eligible_checkins(
                list(observations),
                tenant_id=auth.tenant_id,
                owner_id=auth.owner_id,
                application_id=auth.application_id,
            )
            baseline_cohort, prospective_cohort = split_by_cutoff(
                eligibility.eligible,
                baseline_cutoff=experiment.baseline_cutoff,
                prospective_start=experiment.prospective_start,
            )

            phase_value = command.phase.value
            cohort = (
                baseline_cohort
                if command.phase is EvidencePhase.BASELINE_EXPLORATORY
                else prospective_cohort
            )
            sufficient_obs, below_obs = partition_exposure(cohort, experiment.sleep_threshold_hours)
            n_sufficient = len(sufficient_obs)
            n_below = len(below_obs)

            deadline = experiment.prospective_start + timedelta(days=experiment.maximum_window_days)
            expired = (
                command.phase is EvidencePhase.PROSPECTIVE_VALIDATION
                and now > deadline
                and (n_sufficient < MINIMUM_GROUP_SIZE or n_below < MINIMUM_GROUP_SIZE)
            )

            analysis_result_dict: dict[str, object] | None = None
            model_probability = 0.5
            ci_low = 0.0
            ci_high = 0.0
            estimated_effect = 0.0
            p_delta_gt_0 = 0.5
            p_delta_ge_mmd = 0.0

            if n_sufficient > 0 and n_below > 0:
                seed = derive_seed(
                    experiment.experiment_id,
                    experiment.protocol_version,
                    phase_value,
                )
                bootstrap = bayesian_bootstrap_difference_in_means(
                    sufficient=[o.productivity for o in sufficient_obs],
                    below=[o.productivity for o in below_obs],
                    minimum_meaningful_difference=experiment.minimum_meaningful_difference,
                    seed=seed,
                )
                analysis_result_dict = {
                    "method": bootstrap.method,
                    "draws": bootstrap.draws,
                    "seed": bootstrap.seed,
                    "posterior_median_delta": bootstrap.posterior_median_delta,
                    "posterior_mean_delta": bootstrap.posterior_mean_delta,
                    "credible_interval_90_low": bootstrap.credible_interval_90_low,
                    "credible_interval_90_high": bootstrap.credible_interval_90_high,
                    "credible_interval_95_low": bootstrap.credible_interval_95_low,
                    "credible_interval_95_high": bootstrap.credible_interval_95_high,
                    "p_delta_gt_0": bootstrap.p_delta_gt_0,
                    "p_delta_ge_mmd": bootstrap.p_delta_ge_mmd,
                    "mean_sufficient": bootstrap.mean_sufficient,
                    "mean_below": bootstrap.mean_below,
                    "n_sufficient": bootstrap.n_sufficient,
                    "n_below": bootstrap.n_below,
                }
                model_probability = bootstrap.p_delta_gt_0
                ci_low = bootstrap.credible_interval_90_low
                ci_high = bootstrap.credible_interval_90_high
                estimated_effect = bootstrap.posterior_median_delta
                p_delta_gt_0 = bootstrap.p_delta_gt_0
                p_delta_ge_mmd = bootstrap.p_delta_ge_mmd

            belief_state_str = classify_belief_state(
                phase=phase_value,
                n_sufficient=n_sufficient,
                n_below=n_below,
                p_delta_gt_0=p_delta_gt_0,
                p_delta_ge_mmd=p_delta_ge_mmd,
                ci90_low=ci_low,
                expired=expired,
            )
            belief_state = BeliefState(belief_state_str)

            # Constitutional guard: baseline never reaches PROSPECTIVE_SUPPORTED.
            if (
                command.phase is EvidencePhase.BASELINE_EXPLORATORY
                and belief_state is BeliefState.PROSPECTIVE_SUPPORTED
            ):
                belief_state = BeliefState.EXPLORATORY_POSITIVE
                belief_state_str = belief_state.value

            limitations = (OBSERVATIONAL_LIMITATION,)
            confounding = tuple(confounding_diagnostics(sufficient_obs, below_obs))
            source_obs_ids = tuple(o.observation_id for o in cohort)
            source_event_ids = tuple(o.event_id for o in cohort)
            source_hash = _source_hash(source_obs_ids)

            prior_belief = uow.epistemic.get_current_belief(
                auth.owner_id, auth.application_id, experiment.hypothesis_id
            )
            total_n = n_sufficient + n_below

            evidence_event = _append_event(
                uow,
                auth=auth,
                event_type="EvidenceEvaluated",
                aggregate_type=EVIDENCE_AGGREGATE,
                aggregate_id=evidence_id,
                aggregate_version=1,
                payload={
                    "evidence_id": evidence_id,
                    "hypothesis_id": experiment.hypothesis_id,
                    "experiment_id": experiment.experiment_id,
                    "phase": phase_value,
                    "source_observation_ids": list(source_obs_ids),
                    "source_event_ids": list(source_event_ids),
                    "source_hash": source_hash,
                    "eligible_count": len(eligibility.eligible),
                    "excluded_count": eligibility.excluded_count,
                    "exclusion_reasons": eligibility.exclusion_reasons,
                    "group_counts": {
                        "SUFFICIENT": n_sufficient,
                        "BELOW_THRESHOLD": n_below,
                    },
                    "analysis_result": analysis_result_dict,
                    "belief_state": belief_state_str,
                    "limitations": list(limitations),
                    "descriptive_statistics": {
                        "baseline_eligible": len(baseline_cohort),
                        "prospective_eligible": len(prospective_cohort),
                    },
                    "analysis_parameters": {
                        "sleep_threshold_hours": experiment.sleep_threshold_hours,
                        "minimum_meaningful_difference": experiment.minimum_meaningful_difference,
                    },
                    "confounding_diagnostics": list(confounding),
                },
                audit_id=audit_id,
                request_id=command.request_id,
                idempotency_key=command.idempotency_key,
                occurred_at=now,
            )

            belief_event_type = "BeliefCreated" if prior_belief is None else "BeliefUpdated"
            belief_payload: dict[str, object] = {
                "belief_id": belief_id,
                "hypothesis_id": experiment.hypothesis_id,
                "evidence_id": evidence_id,
                "belief_state": belief_state_str,
                "model_probability": model_probability,
                "estimated_effect": estimated_effect,
                "calibration_state": CalibrationState.UNCALIBRATED.value,
                "causality_level": CausalityLevel.CORRELATION.value,
                "credible_interval_low": ci_low,
                "credible_interval_high": ci_high,
                "minimum_meaningful_difference": experiment.minimum_meaningful_difference,
                "data_confidence": _data_confidence(total_n).value,
                "method_confidence": ConfidenceLevel.MODERATE.value,
                "conclusion_confidence": _conclusion_confidence(belief_state).value,
                "recommendation_confidence": ConfidenceLevel.VERY_LOW.value,
                "limitations": list(limitations),
            }
            if prior_belief is not None:
                belief_payload["previous_belief_id"] = prior_belief.belief_id

            belief_event = _append_event(
                uow,
                auth=auth,
                event_type=belief_event_type,
                aggregate_type=BELIEF_AGGREGATE,
                aggregate_id=belief_id,
                aggregate_version=1,
                payload=belief_payload,
                audit_id=audit_id,
                request_id=command.request_id,
                idempotency_key=None,
                occurred_at=now,
            )

            event_ids: list[str] = [evidence_event.event_id, belief_event.event_id]
            output_ids: list[str] = [evidence_id, belief_id]

            if command.phase is EvidencePhase.PROSPECTIVE_VALIDATION:
                outcome_id = new_id(OUTCOME_PREFIX)
                prior_state = BeliefState(prior_belief.belief_state) if prior_belief else None
                agreement = agreement_with_prior(prior_state, belief_state)
                outcome_event = _append_event(
                    uow,
                    auth=auth,
                    event_type="OutcomeEvaluated",
                    aggregate_type=OUTCOME_AGGREGATE,
                    aggregate_id=outcome_id,
                    aggregate_version=1,
                    payload={
                        "outcome_evaluation_id": outcome_id,
                        "hypothesis_id": experiment.hypothesis_id,
                        "experiment_id": experiment.experiment_id,
                        "prior_belief_id": prior_belief.belief_id if prior_belief else None,
                        "validation_evidence_id": evidence_id,
                        "validation_result": belief_state_str,
                        "agreement_with_prior": agreement.value,
                        "outcome_state": belief_state_str,
                    },
                    audit_id=audit_id,
                    request_id=command.request_id,
                    idempotency_key=None,
                    occurred_at=now,
                )
                event_ids.append(outcome_event.event_id)
                output_ids.append(outcome_id)

                change_type, what, why, remains, next_needed = learning_texts(
                    agreement=agreement,
                    prior_state=prior_state,
                    new_state=belief_state,
                    prior_p=prior_belief.model_probability if prior_belief else None,
                    new_p=model_probability,
                )
                learning_id = new_id(LEARNING_PREFIX)
                learning_event = _append_event(
                    uow,
                    auth=auth,
                    event_type="LearningRecorded",
                    aggregate_type=LEARNING_AGGREGATE,
                    aggregate_id=learning_id,
                    aggregate_version=1,
                    payload={
                        "learning_id": learning_id,
                        "hypothesis_id": experiment.hypothesis_id,
                        "previous_belief_id": prior_belief.belief_id if prior_belief else None,
                        "new_belief_id": belief_id,
                        "outcome_evaluation_id": outcome_id,
                        "change_type": change_type.value,
                        "what_changed": what,
                        "why_changed": why,
                        "what_remains_unknown": remains,
                        "next_evidence_needed": next_needed,
                    },
                    audit_id=audit_id,
                    request_id=command.request_id,
                    idempotency_key=None,
                    occurred_at=now,
                )
                event_ids.append(learning_event.event_id)
                output_ids.append(learning_id)
                if learning_event.global_position is None:
                    raise RuntimeError("persisted event missing global_position")
                uow.epistemic.append_learning_record(
                    ProjectedLearningRecord(
                        learning_id=learning_id,
                        tenant_id=auth.tenant_id,
                        owner_id=auth.owner_id,
                        application_id=auth.application_id,
                        hypothesis_id=experiment.hypothesis_id,
                        previous_belief_id=prior_belief.belief_id if prior_belief else None,
                        new_belief_id=belief_id,
                        outcome_evaluation_id=outcome_id,
                        change_type=change_type.value,
                        what_changed=what,
                        why_changed=why,
                        what_remains_unknown=remains,
                        next_evidence_needed=next_needed,
                        created_at=now,
                        audit_id=audit_id,
                        event_id=learning_event.event_id,
                        global_position=learning_event.global_position,
                    )
                )

            if evidence_event.global_position is None or belief_event.global_position is None:
                raise RuntimeError("persisted event missing global_position")

            uow.epistemic.upsert_evidence_snapshot(
                ProjectedEvidenceSnapshot(
                    evidence_id=evidence_id,
                    tenant_id=auth.tenant_id,
                    owner_id=auth.owner_id,
                    application_id=auth.application_id,
                    hypothesis_id=experiment.hypothesis_id,
                    experiment_id=experiment.experiment_id,
                    phase=phase_value,
                    source_observation_ids=source_obs_ids,
                    source_event_ids=source_event_ids,
                    source_hash=source_hash,
                    eligible_count=len(eligibility.eligible),
                    excluded_count=eligibility.excluded_count,
                    exclusion_reasons=eligibility.exclusion_reasons,
                    group_counts={"SUFFICIENT": n_sufficient, "BELOW_THRESHOLD": n_below},
                    descriptive_statistics={
                        "baseline_eligible": len(baseline_cohort),
                        "prospective_eligible": len(prospective_cohort),
                    },
                    analysis_parameters={
                        "sleep_threshold_hours": experiment.sleep_threshold_hours,
                        "minimum_meaningful_difference": experiment.minimum_meaningful_difference,
                    },
                    analysis_result=analysis_result_dict,
                    confounding_diagnostics=confounding,
                    limitations=limitations,
                    belief_state=belief_state_str,
                    generated_at=now,
                    audit_id=audit_id,
                    event_id=evidence_event.event_id,
                    global_position=evidence_event.global_position,
                )
            )

            uow.epistemic.upsert_belief_snapshot(
                ProjectedBeliefSnapshot(
                    belief_id=belief_id,
                    tenant_id=auth.tenant_id,
                    owner_id=auth.owner_id,
                    application_id=auth.application_id,
                    hypothesis_id=experiment.hypothesis_id,
                    evidence_id=evidence_id,
                    previous_belief_id=prior_belief.belief_id if prior_belief else None,
                    belief_state=belief_state_str,
                    model_probability=model_probability,
                    credible_interval_low=ci_low,
                    credible_interval_high=ci_high,
                    estimated_effect=estimated_effect,
                    minimum_meaningful_difference=experiment.minimum_meaningful_difference,
                    data_confidence=_data_confidence(total_n).value,
                    method_confidence=ConfidenceLevel.MODERATE.value,
                    conclusion_confidence=_conclusion_confidence(belief_state).value,
                    recommendation_confidence=ConfidenceLevel.VERY_LOW.value,
                    calibration_state=CalibrationState.UNCALIBRATED.value,
                    causality_level=CausalityLevel.CORRELATION.value,
                    limitations=limitations,
                    is_current=True,
                    created_at=now,
                    audit_id=audit_id,
                    event_id=belief_event.event_id,
                    global_position=belief_event.global_position,
                )
            )

            window_remaining = max(0, (deadline - now).days)
            exp_status = experiment.status
            if command.phase is EvidencePhase.BASELINE_EXPLORATORY:
                hyp_status = HypothesisStatus.OBSERVING.value
            else:
                hyp_status = HypothesisStatus.EVALUATED.value
                if belief_state in {
                    BeliefState.PROSPECTIVE_SUPPORTED,
                    BeliefState.PROSPECTIVE_WEAKENED,
                }:
                    exp_status = "COMPLETED"
                elif expired:
                    exp_status = "EXPIRED"
                else:
                    exp_status = "IN_PROGRESS"

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
                    status=hyp_status,
                    human_confirmed=hypothesis.human_confirmed,
                    parameters=hypothesis.parameters,
                    proposed_at=hypothesis.proposed_at,
                    activated_at=hypothesis.activated_at,
                    retired_at=hypothesis.retired_at,
                    experiment_id=hypothesis.experiment_id,
                    audit_id=audit_id,
                    event_id=evidence_event.event_id,
                    global_position=evidence_event.global_position,
                    updated_at=now,
                )
            )
            uow.epistemic.upsert_experiment(
                ProjectedExperiment(
                    experiment_id=experiment.experiment_id,
                    tenant_id=experiment.tenant_id,
                    owner_id=experiment.owner_id,
                    application_id=experiment.application_id,
                    hypothesis_id=experiment.hypothesis_id,
                    protocol_version=experiment.protocol_version,
                    analysis_method=experiment.analysis_method,
                    baseline_cutoff=experiment.baseline_cutoff,
                    prospective_start=experiment.prospective_start,
                    prospective_target=experiment.prospective_target,
                    maximum_window_days=experiment.maximum_window_days,
                    minimum_group_size=experiment.minimum_group_size,
                    minimum_meaningful_difference=experiment.minimum_meaningful_difference,
                    sleep_threshold_hours=experiment.sleep_threshold_hours,
                    random_seed_policy=experiment.random_seed_policy,
                    status=exp_status,
                    pre_registered_at=experiment.pre_registered_at,
                    audit_id=audit_id,
                    event_id=evidence_event.event_id,
                    global_position=evidence_event.global_position,
                    updated_at=now,
                )
            )

            base_suf, base_below = partition_exposure(
                baseline_cohort, experiment.sleep_threshold_hours
            )
            pro_suf, pro_below = partition_exposure(
                prospective_cohort, experiment.sleep_threshold_hours
            )
            uow.epistemic.upsert_experiment_progress(
                ProjectedExperimentProgress(
                    experiment_id=experiment.experiment_id,
                    hypothesis_id=experiment.hypothesis_id,
                    tenant_id=auth.tenant_id,
                    owner_id=auth.owner_id,
                    application_id=auth.application_id,
                    baseline_eligible=len(baseline_cohort),
                    baseline_sufficient=len(base_suf),
                    baseline_below=len(base_below),
                    prospective_eligible=len(prospective_cohort),
                    prospective_sufficient=len(pro_suf),
                    prospective_below=len(pro_below),
                    prospective_target=experiment.prospective_target,
                    window_days_remaining=window_remaining,
                    status=exp_status,
                    current_belief_state=belief_state_str,
                    last_evaluated_at=now,
                    updated_at=now,
                )
            )

            _append_audit(
                uow,
                auth=auth,
                audit_id=audit_id,
                request_id=command.request_id,
                action=EVALUATE_EXPERIMENT_ACTION,
                engine_version=self._engine_version,
                api_version=self._api_version,
                health_provider=self._health,
                input_ids=(experiment.experiment_id,),
                output_ids=tuple(output_ids),
                event_ids=tuple(event_ids),
            )
            self._store_idempotency(
                uow,
                auth,
                command.idempotency_key,
                payload_hash,
                evidence_id,
                belief_id,
                audit_id,
            )
            uow.commit()

        return EvaluateExperimentResult(
            experiment_id=command.experiment_id,
            evidence_id=evidence_id,
            belief_id=belief_id,
            belief_state=belief_state_str,
            event_id=evidence_event.event_id,
            audit_id=audit_id,
            replayed=False,
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
