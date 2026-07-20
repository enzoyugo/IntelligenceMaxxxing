"""Stage 3.1 EvaluateExperimentUseCase — temporal, terminal, semantic idempotency."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

from intelligence_maxxxing.application.auth.service import AuthContext
from intelligence_maxxxing.application.errors import (
    ExperimentNotFoundError,
    HypothesisNotFoundError,
    HypothesisStateError,
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
from intelligence_maxxxing.domain.common.identifiers import (
    AUDIT_PREFIX,
    BELIEF_PREFIX,
    EVIDENCE_PREFIX,
    LEARNING_PREFIX,
    OUTCOME_PREFIX,
    new_id,
)
from intelligence_maxxxing.domain_packs.life.eligibility import (
    ANALYSIS_METHOD,
    OBSERVATIONAL_LIMITATION,
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
from intelligence_maxxxing.domain_packs.life.learning_templates import (
    agreement_with_prior,
    learning_texts,
)
from intelligence_maxxxing.domain_packs.life.methods.bayesian_bootstrap import (
    bayesian_bootstrap_difference_in_means,
    classify_belief_state,
    derive_seed,
)
from intelligence_maxxxing.domain_packs.life.observation_scan import scan_all_life_observations
from intelligence_maxxxing.infrastructure.clock.system_clock import SystemClock


def _helpers() -> Any:
    """Lazy import to avoid circular dependency with epistemic.py re-export."""
    from intelligence_maxxxing.application.use_cases import epistemic as ep

    return ep


MINIMUM_GROUP_SIZE = 7


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
    evaluation_kind: str
    terminal: bool
    terminal_reason: str | None = None
    prospective_eligible: int = 0
    prospective_target: int = 0
    target_remaining: int = 0
    sufficient_count: int = 0
    below_count: int = 0
    sufficient_remaining: int = 0
    below_remaining: int = 0
    future_excluded: int = 0
    duplicate_source_excluded: int = 0
    critical_data_quality_failure: bool = False


def _terminal_states() -> set[BeliefState]:
    return {
        BeliefState.PROSPECTIVE_SUPPORTED,
        BeliefState.PROSPECTIVE_WEAKENED,
        BeliefState.PROSPECTIVE_INCONCLUSIVE,
        BeliefState.EXPIRED_INCONCLUSIVE,
    }


class EvaluateExperimentUseCase:
    def __init__(
        self,
        uow: UnitOfWorkPort,
        engine_version: str,
        api_version: str,
        health_provider: HealthSnapshotProviderPort,
        clock: ClockPort | None = None,
    ) -> None:
        ep = _helpers()
        self._uow = uow
        self._engine_version = engine_version
        self._api_version = api_version
        self._health = health_provider
        self._clock = clock or SystemClock()
        self._action = ep.EVALUATE_EXPERIMENT_ACTION
        self._result_factory = None
        self._ep = ep

    def _find_existing(self, command: BaseModel, auth: AuthContext, payload_hash: str, idempotency_key: str) -> Any:
        return self._ep.IdempotentWriteMixin._find_existing(self, command, auth, payload_hash, idempotency_key)

    def _resolve_race(self, command: BaseModel, auth: AuthContext, payload_hash: str, idempotency_key: str) -> Any:
        return self._ep.IdempotentWriteMixin._resolve_race(self, command, auth, payload_hash, idempotency_key)

    def _store_idempotency(self, uow: UnitOfWorkPort, auth: AuthContext, idempotency_key: str, payload_hash: str, primary_id: str, event_id: str, audit_id: str) -> None:
        return self._ep.IdempotentWriteMixin._store_idempotency(
            self, uow, auth, idempotency_key, payload_hash, primary_id, event_id, audit_id
        )

    def execute(
        self, command: EvaluateExperimentCommand, auth: AuthContext
    ) -> EvaluateExperimentResult:
        payload_hash = self._ep._payload_hash(command)
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
            evidence = uow.epistemic.get_evidence_snapshot(
                auth.owner_id, auth.application_id, record.observation_id
            )
            belief = uow.epistemic.get_belief_snapshot(
                auth.owner_id, auth.application_id, record.event_id
            )
            progress = uow.epistemic.get_experiment_progress(
                auth.owner_id, auth.application_id, experiment_id
            )
            uow.commit()
        return self._result_from_rows(
            experiment_id=experiment_id,
            evidence=evidence,
            belief=belief,
            progress=progress,
            audit_id=record.audit_id,
            replayed=True,
        )

    def _result_from_rows(
        self,
        *,
        experiment_id: str,
        evidence: ProjectedEvidenceSnapshot | None,
        belief: ProjectedBeliefSnapshot | None,
        progress: ProjectedExperimentProgress | None,
        audit_id: str,
        replayed: bool,
    ) -> EvaluateExperimentResult:
        pro_el = progress.prospective_eligible if progress else 0
        target = progress.prospective_target if progress else 0
        suf = progress.prospective_sufficient if progress else 0
        bel = progress.prospective_below if progress else 0
        min_g = progress.minimum_group_size if progress and progress.minimum_group_size else MINIMUM_GROUP_SIZE
        return EvaluateExperimentResult(
            experiment_id=experiment_id,
            evidence_id=evidence.evidence_id if evidence else "",
            belief_id=belief.belief_id if belief else "",
            belief_state=belief.belief_state if belief else (evidence.belief_state if evidence else ""),
            event_id=evidence.event_id if evidence else "",
            audit_id=audit_id,
            replayed=replayed,
            evaluation_kind=(
                evidence.evaluation_kind
                if evidence and evidence.evaluation_kind
                else EvaluationKind.INTERIM_EVALUATION.value
            ),
            terminal=bool(evidence.terminal) if evidence else False,
            terminal_reason=evidence.terminal_reason if evidence else None,
            prospective_eligible=pro_el,
            prospective_target=target,
            target_remaining=max(0, target - pro_el),
            sufficient_count=suf,
            below_count=bel,
            sufficient_remaining=max(0, min_g - suf),
            below_remaining=max(0, min_g - bel),
            future_excluded=progress.future_excluded if progress else 0,
            duplicate_source_excluded=progress.duplicate_source_excluded if progress else 0,
            critical_data_quality_failure=(
                bool(progress.critical_data_quality_failure) if progress else False
            ),
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

            now = self._clock.now()
            evaluation_started_at = now
            head = uow.integrity.get_stream_head(
                auth.tenant_id, auth.owner_id, auth.application_id
            )
            evidence_cutoff_global_position = (
                int(head.last_global_position) if head is not None else 0
            )
            evidence_cutoff_recorded_at = now

            activation_global_position = (
                experiment.activation_global_position
                if experiment.activation_global_position is not None
                else experiment.global_position
            )
            activation_recorded_at = experiment.activation_recorded_at or experiment.pre_registered_at

            observations = scan_all_life_observations(
                uow.projections,
                owner_id=auth.owner_id,
                application_id=auth.application_id,
                max_global_position=evidence_cutoff_global_position,
            )
            eligibility = select_eligible_checkins(
                list(observations),
                tenant_id=auth.tenant_id,
                owner_id=auth.owner_id,
                application_id=auth.application_id,
            )
            baseline_cohort, prospective_cohort, temporal_exclusions = split_by_temporal_anchors(
                eligibility.eligible,
                baseline_cutoff=experiment.baseline_cutoff,
                prospective_start=experiment.prospective_start,
                activation_global_position=activation_global_position,
                activation_recorded_at=activation_recorded_at,
                evidence_cutoff_global_position=evidence_cutoff_global_position,
                evidence_cutoff_recorded_at=evidence_cutoff_recorded_at,
                evaluation_started_at=evaluation_started_at,
            )
            merged_exclusions = dict(eligibility.exclusion_reasons)
            for k, v in temporal_exclusions.items():
                merged_exclusions[k] = merged_exclusions.get(k, 0) + v
            excluded_count = eligibility.excluded_count + sum(temporal_exclusions.values())
            future_excluded = temporal_exclusions.get("OCCURRED_AT_IN_FUTURE", 0)
            duplicate_source_excluded = eligibility.exclusion_reasons.get(
                "DUPLICATE_LOGICAL_SOURCE", 0
            ) + eligibility.exclusion_reasons.get("DUPLICATE_SOURCE_CONFLICT", 0)

            phase_value = command.phase.value
            cohort = (
                baseline_cohort
                if command.phase is EvidencePhase.BASELINE_EXPLORATORY
                else prospective_cohort
            )
            sufficient_obs, below_obs = partition_exposure(cohort, experiment.sleep_threshold_hours)
            n_sufficient = len(sufficient_obs)
            n_below = len(below_obs)
            prospective_total = len(prospective_cohort)

            deadline = experiment.prospective_start + timedelta(days=experiment.maximum_window_days)
            expired = command.phase is EvidencePhase.PROSPECTIVE_VALIDATION and now > deadline

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

            critical_dq = eligibility.critical_data_quality_failure
            belief_state_str = classify_belief_state(
                phase=phase_value,
                n_sufficient=n_sufficient,
                n_below=n_below,
                p_delta_gt_0=p_delta_gt_0,
                p_delta_ge_mmd=p_delta_ge_mmd,
                ci90_low=ci_low,
                expired=expired,
                prospective_target=experiment.prospective_target,
                critical_data_quality_failure=critical_dq,
            )
            belief_state = BeliefState(belief_state_str)

            if (
                command.phase is EvidencePhase.BASELINE_EXPLORATORY
                and belief_state is BeliefState.PROSPECTIVE_SUPPORTED
            ):
                belief_state = BeliefState.EXPLORATORY_POSITIVE
                belief_state_str = belief_state.value

            terminal = False
            terminal_reason: str | None = TerminalReason.NOT_TERMINAL.value
            if command.phase is EvidencePhase.PROSPECTIVE_VALIDATION:
                if critical_dq and expired:
                    terminal = True
                    terminal_reason = TerminalReason.DATA_QUALITY_TERMINATION.value
                    belief_state = BeliefState.EXPIRED_INCONCLUSIVE
                    belief_state_str = belief_state.value
                elif belief_state is BeliefState.EXPIRED_INCONCLUSIVE:
                    terminal = True
                    terminal_reason = TerminalReason.MAXIMUM_WINDOW_EXPIRED.value
                elif belief_state in _terminal_states() and belief_state is not BeliefState.EXPIRED_INCONCLUSIVE:
                    terminal = True
                    terminal_reason = TerminalReason.TARGET_REACHED.value
                else:
                    terminal = False
                    terminal_reason = TerminalReason.NOT_TERMINAL.value
                    belief_state = BeliefState.PROSPECTIVE_COLLECTING
                    belief_state_str = belief_state.value

            evaluation_kind = (
                EvaluationKind.TERMINAL_EVALUATION.value
                if terminal
                else EvaluationKind.INTERIM_EVALUATION.value
            )

            limitations = (OBSERVATIONAL_LIMITATION,)
            confounding = tuple(confounding_diagnostics(sufficient_obs, below_obs))
            source_obs_ids = tuple(o.observation_id for o in cohort)
            source_event_ids = tuple(sorted({o.event_id for o in cohort}))
            source_hash = compute_source_hash(source_event_ids)
            source_positions = [o.global_position for o in cohort]
            source_count, first_pos, last_pos = source_position_stats(source_positions)

            analysis_parameters = {
                "sleep_threshold_hours": experiment.sleep_threshold_hours,
                "minimum_meaningful_difference": experiment.minimum_meaningful_difference,
            }
            fingerprint = compute_evidence_fingerprint(
                tenant_id=auth.tenant_id,
                owner_id=auth.owner_id,
                application_id=auth.application_id,
                experiment_id=experiment.experiment_id,
                protocol_version=experiment.protocol_version,
                phase=phase_value,
                evidence_cutoff_global_position=evidence_cutoff_global_position,
                source_event_ids=source_event_ids,
                analysis_method=ANALYSIS_METHOD,
                analysis_parameters=analysis_parameters,
            )

            existing_fp = uow.epistemic.get_evidence_by_fingerprint(
                auth.owner_id,
                auth.application_id,
                experiment.experiment_id,
                phase_value,
                fingerprint,
            )
            if existing_fp is not None:
                belief = uow.epistemic.get_current_belief(
                    auth.owner_id, auth.application_id, experiment.hypothesis_id
                )
                # Prefer belief bound to this evidence.
                for b in uow.epistemic.list_belief_snapshots(
                    auth.owner_id, auth.application_id, experiment.hypothesis_id
                ):
                    if b.evidence_id == existing_fp.evidence_id:
                        belief = b
                        break
                progress = uow.epistemic.get_experiment_progress(
                    auth.owner_id, auth.application_id, experiment.experiment_id
                )
                self._store_idempotency(
                    uow,
                    auth,
                    command.idempotency_key,
                    payload_hash,
                    existing_fp.evidence_id,
                    belief.belief_id if belief else existing_fp.event_id,
                    existing_fp.audit_id,
                )
                uow.commit()
                return self._result_from_rows(
                    experiment_id=experiment.experiment_id,
                    evidence=existing_fp,
                    belief=belief,
                    progress=progress,
                    audit_id=existing_fp.audit_id,
                    replayed=True,
                )

            audit_id = new_id(AUDIT_PREFIX)
            evidence_id = new_id(EVIDENCE_PREFIX)
            belief_id = new_id(BELIEF_PREFIX)
            prior_belief = uow.epistemic.get_current_belief(
                auth.owner_id, auth.application_id, experiment.hypothesis_id
            )
            total_n = n_sufficient + n_below

            evidence_event = self._ep._append_event(
                uow,
                auth=auth,
                event_type="EvidenceEvaluated",
                aggregate_type=self._ep.EVIDENCE_AGGREGATE,
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
                    "excluded_count": excluded_count,
                    "exclusion_reasons": merged_exclusions,
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
                        "evidence_fingerprint": fingerprint,
                        "evaluation_kind": evaluation_kind,
                        "terminal": terminal,
                        "terminal_reason": terminal_reason,
                        "evidence_cutoff_global_position": evidence_cutoff_global_position,
                    },
                    "analysis_parameters": analysis_parameters,
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
                "data_confidence": self._ep._data_confidence(total_n).value,
                "method_confidence": ConfidenceLevel.MODERATE.value,
                "conclusion_confidence": self._ep._conclusion_confidence(belief_state).value,
                "recommendation_confidence": ConfidenceLevel.VERY_LOW.value,
                "limitations": list(limitations),
            }
            if prior_belief is not None:
                belief_payload["previous_belief_id"] = prior_belief.belief_id

            belief_event = self._ep._append_event(
                uow,
                auth=auth,
                event_type=belief_event_type,
                aggregate_type=self._ep.BELIEF_AGGREGATE,
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

            # Terminal prospective only: Outcome + Learning
            if (
                command.phase is EvidencePhase.PROSPECTIVE_VALIDATION
                and terminal
                and belief_state in _terminal_states()
            ):
                outcome_id = new_id(OUTCOME_PREFIX)
                prior_state = BeliefState(prior_belief.belief_state) if prior_belief else None
                agreement = agreement_with_prior(prior_state, belief_state)
                outcome_event = self._ep._append_event(
                    uow,
                    auth=auth,
                    event_type="OutcomeEvaluated",
                    aggregate_type=self._ep.OUTCOME_AGGREGATE,
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
                learning_event = self._ep._append_event(
                    uow,
                    auth=auth,
                    event_type="LearningRecorded",
                    aggregate_type=self._ep.LEARNING_AGGREGATE,
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

            try:
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
                        excluded_count=excluded_count,
                        exclusion_reasons=merged_exclusions,
                        group_counts={"SUFFICIENT": n_sufficient, "BELOW_THRESHOLD": n_below},
                        descriptive_statistics={
                            "baseline_eligible": len(baseline_cohort),
                            "prospective_eligible": len(prospective_cohort),
                        },
                        analysis_parameters=analysis_parameters,
                        analysis_result=analysis_result_dict,
                        confounding_diagnostics=confounding,
                        limitations=limitations,
                        belief_state=belief_state_str,
                        generated_at=now,
                        audit_id=audit_id,
                        event_id=evidence_event.event_id,
                        global_position=evidence_event.global_position,
                        evidence_fingerprint=fingerprint,
                        evidence_cutoff_global_position=evidence_cutoff_global_position,
                        evidence_cutoff_recorded_at=evidence_cutoff_recorded_at,
                        evaluation_started_at=evaluation_started_at,
                        evaluation_kind=evaluation_kind,
                        terminal=terminal,
                        terminal_reason=terminal_reason,
                        critical_data_quality_failure=critical_dq,
                        source_count=source_count,
                        first_source_global_position=first_pos,
                        last_source_global_position=last_pos,
                    )
                )
            except IntegrityError:
                # Concurrent same fingerprint — replay winner.
                session = getattr(uow, "_session", None)
                if session is not None:
                    session.rollback()
                with self._uow as uow2:
                    winner = uow2.epistemic.get_evidence_by_fingerprint(
                        auth.owner_id,
                        auth.application_id,
                        experiment.experiment_id,
                        phase_value,
                        fingerprint,
                    )
                    belief = uow2.epistemic.get_current_belief(
                        auth.owner_id, auth.application_id, experiment.hypothesis_id
                    )
                    progress = uow2.epistemic.get_experiment_progress(
                        auth.owner_id, auth.application_id, experiment.experiment_id
                    )
                    if winner is None:
                        raise
                    self._store_idempotency(
                        uow2,
                        auth,
                        command.idempotency_key,
                        payload_hash,
                        winner.evidence_id,
                        belief.belief_id if belief else winner.event_id,
                        winner.audit_id,
                    )
                    uow2.commit()
                    return self._result_from_rows(
                        experiment_id=experiment.experiment_id,
                        evidence=winner,
                        belief=belief,
                        progress=progress,
                        audit_id=winner.audit_id,
                        replayed=True,
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
                    data_confidence=self._ep._data_confidence(total_n).value,
                    method_confidence=ConfidenceLevel.MODERATE.value,
                    conclusion_confidence=self._ep._conclusion_confidence(belief_state).value,
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
            if command.phase is EvidencePhase.BASELINE_EXPLORATORY:
                hyp_status = HypothesisStatus.OBSERVING.value
                exp_status = "COLLECTING_BASELINE"
            elif terminal:
                hyp_status = HypothesisStatus.EVALUATED.value
                if belief_state is BeliefState.PROSPECTIVE_SUPPORTED:
                    exp_status = "TERMINAL_SUPPORTED"
                elif belief_state is BeliefState.PROSPECTIVE_WEAKENED:
                    exp_status = "TERMINAL_WEAKENED"
                elif belief_state is BeliefState.EXPIRED_INCONCLUSIVE:
                    exp_status = "EXPIRED_INCONCLUSIVE"
                else:
                    exp_status = "TERMINAL_INCONCLUSIVE"
            else:
                hyp_status = HypothesisStatus.OBSERVING.value
                exp_status = "PROSPECTIVE_COLLECTING"

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
                    activation_event_id=experiment.activation_event_id,
                    activation_global_position=experiment.activation_global_position,
                    activation_recorded_at=experiment.activation_recorded_at,
                )
            )

            base_suf, base_below = partition_exposure(
                baseline_cohort, experiment.sleep_threshold_hours
            )
            pro_suf, pro_below = partition_exposure(
                prospective_cohort, experiment.sleep_threshold_hours
            )
            target_remaining = max(0, experiment.prospective_target - prospective_total)
            progress_row = ProjectedExperimentProgress(
                experiment_id=experiment.experiment_id,
                hypothesis_id=experiment.hypothesis_id,
                tenant_id=auth.tenant_id,
                owner_id=auth.owner_id,
                application_id=auth.application_id,
                baseline_eligible=len(baseline_cohort),
                baseline_sufficient=len(base_suf),
                baseline_below=len(base_below),
                prospective_eligible=prospective_total,
                prospective_sufficient=len(pro_suf),
                prospective_below=len(pro_below),
                prospective_target=experiment.prospective_target,
                window_days_remaining=window_remaining,
                status=exp_status,
                current_belief_state=belief_state_str,
                last_evaluated_at=now,
                updated_at=now,
                target_remaining=target_remaining,
                sufficient_remaining=max(0, experiment.minimum_group_size - len(pro_suf)),
                below_remaining=max(0, experiment.minimum_group_size - len(pro_below)),
                future_excluded=future_excluded,
                duplicate_source_excluded=duplicate_source_excluded,
                critical_data_quality_failure=critical_dq,
                evaluation_kind=evaluation_kind,
                terminal=terminal,
                terminal_reason=terminal_reason,
                minimum_group_size=experiment.minimum_group_size,
            )
            uow.epistemic.upsert_experiment_progress(progress_row)

            self._ep._append_audit(
                uow,
                auth=auth,
                audit_id=audit_id,
                request_id=command.request_id,
                action=self._ep.EVALUATE_EXPERIMENT_ACTION,
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

        evidence_view = ProjectedEvidenceSnapshot(
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
            excluded_count=excluded_count,
            exclusion_reasons=merged_exclusions,
            group_counts={"SUFFICIENT": n_sufficient, "BELOW_THRESHOLD": n_below},
            belief_state=belief_state_str,
            generated_at=now,
            audit_id=audit_id,
            event_id=evidence_event.event_id,
            global_position=evidence_event.global_position or 0,
            evaluation_kind=evaluation_kind,
            terminal=terminal,
            terminal_reason=terminal_reason,
            critical_data_quality_failure=critical_dq,
            evidence_fingerprint=fingerprint,
        )
        return EvaluateExperimentResult(
            experiment_id=command.experiment_id,
            evidence_id=evidence_id,
            belief_id=belief_id,
            belief_state=belief_state_str,
            event_id=evidence_event.event_id,
            audit_id=audit_id,
            replayed=False,
            evaluation_kind=evaluation_kind,
            terminal=terminal,
            terminal_reason=terminal_reason,
            prospective_eligible=prospective_total,
            prospective_target=experiment.prospective_target,
            target_remaining=target_remaining,
            sufficient_count=len(pro_suf),
            below_count=len(pro_below),
            sufficient_remaining=max(0, experiment.minimum_group_size - len(pro_suf)),
            below_remaining=max(0, experiment.minimum_group_size - len(pro_below)),
            future_excluded=future_excluded,
            duplicate_source_excluded=duplicate_source_excluded,
            critical_data_quality_failure=critical_dq,
        )
