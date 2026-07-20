"""SQLAlchemy epistemic projections (Stage 3 first epistemic loop).

Derived, rebuildable state: hypotheses, experiments, beliefs, evidence, learning.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from intelligence_maxxxing.application.ports import (
    EpistemicStorePort,
    ProjectedBeliefSnapshot,
    ProjectedEvidenceSnapshot,
    ProjectedExperiment,
    ProjectedExperimentProgress,
    ProjectedHypothesis,
    ProjectedLearningRecord,
)
from intelligence_maxxxing.infrastructure.database.tables import (
    BeliefSnapshotRow,
    CurrentExperimentRow,
    CurrentHypothesisRow,
    EvidenceSnapshotRow,
    ExperimentProgressRow,
    LearningHistoryRow,
)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _as_utc_opt(value: datetime | None) -> datetime | None:
    return None if value is None else _as_utc(value)


class SqlAlchemyEpistemicStore(EpistemicStorePort):
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_hypothesis(self, row: ProjectedHypothesis) -> None:
        existing = self._session.get(CurrentHypothesisRow, row.hypothesis_id)
        if existing is None:
            self._session.add(_hypothesis_to_row(row))
            return
        existing.tenant_id = row.tenant_id
        existing.owner_id = row.owner_id
        existing.application_id = row.application_id
        existing.domain_pack = row.domain_pack
        existing.template_id = row.template_id
        existing.template_version = row.template_version
        existing.statement = row.statement
        existing.direction = row.direction
        existing.causality_level = row.causality_level
        existing.status = row.status
        existing.human_confirmed = 1 if row.human_confirmed else 0
        existing.parameters_json = dict(row.parameters) if row.parameters else None
        existing.proposed_at = row.proposed_at
        existing.activated_at = row.activated_at
        existing.retired_at = row.retired_at
        existing.experiment_id = row.experiment_id
        existing.audit_id = row.audit_id
        existing.event_id = row.event_id
        existing.global_position = row.global_position
        existing.updated_at = row.updated_at

    def get_hypothesis(
        self, owner_id: str, application_id: str, hypothesis_id: str
    ) -> ProjectedHypothesis | None:
        stmt = select(CurrentHypothesisRow).where(
            CurrentHypothesisRow.hypothesis_id == hypothesis_id,
            CurrentHypothesisRow.owner_id == owner_id,
            CurrentHypothesisRow.application_id == application_id,
        )
        row = self._session.scalars(stmt).first()
        return None if row is None else _hypothesis_from_row(row)

    def list_hypotheses(
        self, owner_id: str, application_id: str, *, limit: int = 50
    ) -> Sequence[ProjectedHypothesis]:
        stmt = (
            select(CurrentHypothesisRow)
            .where(
                CurrentHypothesisRow.owner_id == owner_id,
                CurrentHypothesisRow.application_id == application_id,
            )
            .order_by(CurrentHypothesisRow.global_position.desc())
            .limit(limit)
        )
        return [_hypothesis_from_row(r) for r in self._session.scalars(stmt)]

    def upsert_experiment(self, row: ProjectedExperiment) -> None:
        existing = self._session.get(CurrentExperimentRow, row.experiment_id)
        if existing is None:
            self._session.add(_experiment_to_row(row))
            return
        existing.tenant_id = row.tenant_id
        existing.owner_id = row.owner_id
        existing.application_id = row.application_id
        existing.hypothesis_id = row.hypothesis_id
        existing.protocol_version = row.protocol_version
        existing.analysis_method = row.analysis_method
        existing.baseline_cutoff = row.baseline_cutoff
        existing.prospective_start = row.prospective_start
        existing.prospective_target = row.prospective_target
        existing.maximum_window_days = row.maximum_window_days
        existing.minimum_group_size = row.minimum_group_size
        existing.minimum_meaningful_difference = row.minimum_meaningful_difference
        existing.sleep_threshold_hours = row.sleep_threshold_hours
        existing.random_seed_policy = row.random_seed_policy
        existing.status = row.status
        existing.pre_registered_at = row.pre_registered_at
        existing.audit_id = row.audit_id
        existing.event_id = row.event_id
        existing.global_position = row.global_position
        existing.updated_at = row.updated_at

    def get_experiment(
        self, owner_id: str, application_id: str, experiment_id: str
    ) -> ProjectedExperiment | None:
        stmt = select(CurrentExperimentRow).where(
            CurrentExperimentRow.experiment_id == experiment_id,
            CurrentExperimentRow.owner_id == owner_id,
            CurrentExperimentRow.application_id == application_id,
        )
        row = self._session.scalars(stmt).first()
        return None if row is None else _experiment_from_row(row)

    def get_experiment_for_hypothesis(
        self, owner_id: str, application_id: str, hypothesis_id: str
    ) -> ProjectedExperiment | None:
        stmt = select(CurrentExperimentRow).where(
            CurrentExperimentRow.hypothesis_id == hypothesis_id,
            CurrentExperimentRow.owner_id == owner_id,
            CurrentExperimentRow.application_id == application_id,
        )
        row = self._session.scalars(stmt).first()
        return None if row is None else _experiment_from_row(row)

    def upsert_belief_snapshot(self, row: ProjectedBeliefSnapshot) -> None:
        self._session.execute(
            update(BeliefSnapshotRow)
            .where(
                BeliefSnapshotRow.hypothesis_id == row.hypothesis_id,
                BeliefSnapshotRow.owner_id == row.owner_id,
                BeliefSnapshotRow.application_id == row.application_id,
                BeliefSnapshotRow.is_current == 1,
            )
            .values(is_current=0)
        )
        existing = self._session.get(BeliefSnapshotRow, row.belief_id)
        if existing is None:
            self._session.add(_belief_to_row(row))
            return
        existing.tenant_id = row.tenant_id
        existing.owner_id = row.owner_id
        existing.application_id = row.application_id
        existing.hypothesis_id = row.hypothesis_id
        existing.evidence_id = row.evidence_id
        existing.previous_belief_id = row.previous_belief_id
        existing.belief_state = row.belief_state
        existing.model_probability = row.model_probability
        existing.credible_interval_low = row.credible_interval_low
        existing.credible_interval_high = row.credible_interval_high
        existing.estimated_effect = row.estimated_effect
        existing.minimum_meaningful_difference = row.minimum_meaningful_difference
        existing.data_confidence = row.data_confidence
        existing.method_confidence = row.method_confidence
        existing.conclusion_confidence = row.conclusion_confidence
        existing.recommendation_confidence = row.recommendation_confidence
        existing.calibration_state = row.calibration_state
        existing.causality_level = row.causality_level
        existing.limitations_json = list(row.limitations)
        existing.is_current = 1 if row.is_current else 0
        existing.created_at = row.created_at
        existing.audit_id = row.audit_id
        existing.event_id = row.event_id
        existing.global_position = row.global_position

    def get_belief_snapshot(
        self, owner_id: str, application_id: str, belief_id: str
    ) -> ProjectedBeliefSnapshot | None:
        stmt = select(BeliefSnapshotRow).where(
            BeliefSnapshotRow.belief_id == belief_id,
            BeliefSnapshotRow.owner_id == owner_id,
            BeliefSnapshotRow.application_id == application_id,
        )
        row = self._session.scalars(stmt).first()
        return None if row is None else _belief_from_row(row)

    def get_current_belief(
        self, owner_id: str, application_id: str, hypothesis_id: str
    ) -> ProjectedBeliefSnapshot | None:
        stmt = select(BeliefSnapshotRow).where(
            BeliefSnapshotRow.hypothesis_id == hypothesis_id,
            BeliefSnapshotRow.owner_id == owner_id,
            BeliefSnapshotRow.application_id == application_id,
            BeliefSnapshotRow.is_current == 1,
        )
        row = self._session.scalars(stmt).first()
        return None if row is None else _belief_from_row(row)

    def list_belief_snapshots(
        self, owner_id: str, application_id: str, hypothesis_id: str
    ) -> Sequence[ProjectedBeliefSnapshot]:
        stmt = (
            select(BeliefSnapshotRow)
            .where(
                BeliefSnapshotRow.hypothesis_id == hypothesis_id,
                BeliefSnapshotRow.owner_id == owner_id,
                BeliefSnapshotRow.application_id == application_id,
            )
            .order_by(BeliefSnapshotRow.global_position)
        )
        return [_belief_from_row(r) for r in self._session.scalars(stmt)]

    def upsert_evidence_snapshot(self, row: ProjectedEvidenceSnapshot) -> None:
        existing = self._session.get(EvidenceSnapshotRow, row.evidence_id)
        if existing is None:
            self._session.add(_evidence_to_row(row))
            return
        existing.tenant_id = row.tenant_id
        existing.owner_id = row.owner_id
        existing.application_id = row.application_id
        existing.hypothesis_id = row.hypothesis_id
        existing.experiment_id = row.experiment_id
        existing.phase = row.phase
        existing.source_observation_ids = list(row.source_observation_ids)
        existing.source_event_ids = list(row.source_event_ids)
        existing.source_hash = row.source_hash
        existing.eligible_count = row.eligible_count
        existing.excluded_count = row.excluded_count
        existing.exclusion_reasons = dict(row.exclusion_reasons)
        existing.group_counts = dict(row.group_counts)
        existing.descriptive_statistics = dict(row.descriptive_statistics)
        existing.analysis_parameters = dict(row.analysis_parameters)
        existing.analysis_result = (
            dict(row.analysis_result) if row.analysis_result is not None else None
        )
        existing.confounding_diagnostics = list(row.confounding_diagnostics)
        existing.limitations_json = list(row.limitations)
        existing.belief_state = row.belief_state
        existing.generated_at = row.generated_at
        existing.audit_id = row.audit_id
        existing.event_id = row.event_id
        existing.global_position = row.global_position

    def get_evidence_snapshot(
        self, owner_id: str, application_id: str, evidence_id: str
    ) -> ProjectedEvidenceSnapshot | None:
        stmt = select(EvidenceSnapshotRow).where(
            EvidenceSnapshotRow.evidence_id == evidence_id,
            EvidenceSnapshotRow.owner_id == owner_id,
            EvidenceSnapshotRow.application_id == application_id,
        )
        row = self._session.scalars(stmt).first()
        return None if row is None else _evidence_from_row(row)

    def upsert_experiment_progress(self, row: ProjectedExperimentProgress) -> None:
        existing = self._session.get(ExperimentProgressRow, row.experiment_id)
        if existing is None:
            self._session.add(_progress_to_row(row))
            return
        existing.hypothesis_id = row.hypothesis_id
        existing.tenant_id = row.tenant_id
        existing.owner_id = row.owner_id
        existing.application_id = row.application_id
        existing.baseline_eligible = row.baseline_eligible
        existing.baseline_sufficient = row.baseline_sufficient
        existing.baseline_below = row.baseline_below
        existing.prospective_eligible = row.prospective_eligible
        existing.prospective_sufficient = row.prospective_sufficient
        existing.prospective_below = row.prospective_below
        existing.prospective_target = row.prospective_target
        existing.window_days_remaining = row.window_days_remaining
        existing.status = row.status
        existing.current_belief_state = row.current_belief_state
        existing.last_evaluated_at = row.last_evaluated_at
        existing.updated_at = row.updated_at

    def get_experiment_progress(
        self, owner_id: str, application_id: str, experiment_id: str
    ) -> ProjectedExperimentProgress | None:
        stmt = select(ExperimentProgressRow).where(
            ExperimentProgressRow.experiment_id == experiment_id,
            ExperimentProgressRow.owner_id == owner_id,
            ExperimentProgressRow.application_id == application_id,
        )
        row = self._session.scalars(stmt).first()
        return None if row is None else _progress_from_row(row)

    def append_learning_record(self, row: ProjectedLearningRecord) -> None:
        existing = self._session.get(LearningHistoryRow, row.learning_id)
        if existing is not None:
            return
        self._session.add(_learning_to_row(row))

    def list_learning_records(
        self, owner_id: str, application_id: str, hypothesis_id: str
    ) -> Sequence[ProjectedLearningRecord]:
        stmt = (
            select(LearningHistoryRow)
            .where(
                LearningHistoryRow.hypothesis_id == hypothesis_id,
                LearningHistoryRow.owner_id == owner_id,
                LearningHistoryRow.application_id == application_id,
            )
            .order_by(LearningHistoryRow.global_position)
        )
        return [_learning_from_row(r) for r in self._session.scalars(stmt)]

    def delete_all_epistemic_projections(self) -> int:
        counts = 0
        for model in (
            LearningHistoryRow,
            ExperimentProgressRow,
            EvidenceSnapshotRow,
            BeliefSnapshotRow,
            CurrentExperimentRow,
            CurrentHypothesisRow,
        ):
            rows = list(self._session.scalars(select(model)))
            for row in rows:
                self._session.delete(row)
                counts += 1
        return counts

    def list_all_hypotheses(self) -> Sequence[ProjectedHypothesis]:
        stmt = select(CurrentHypothesisRow).order_by(CurrentHypothesisRow.hypothesis_id.asc())
        return [_hypothesis_from_row(r) for r in self._session.scalars(stmt)]

    def list_all_experiments(self) -> Sequence[ProjectedExperiment]:
        stmt = select(CurrentExperimentRow).order_by(CurrentExperimentRow.experiment_id.asc())
        return [_experiment_from_row(r) for r in self._session.scalars(stmt)]

    def list_all_belief_snapshots(self) -> Sequence[ProjectedBeliefSnapshot]:
        stmt = select(BeliefSnapshotRow).order_by(BeliefSnapshotRow.belief_id.asc())
        return [_belief_from_row(r) for r in self._session.scalars(stmt)]

    def list_all_evidence_snapshots(self) -> Sequence[ProjectedEvidenceSnapshot]:
        stmt = select(EvidenceSnapshotRow).order_by(EvidenceSnapshotRow.evidence_id.asc())
        return [_evidence_from_row(r) for r in self._session.scalars(stmt)]

    def list_all_experiment_progress(self) -> Sequence[ProjectedExperimentProgress]:
        stmt = select(ExperimentProgressRow).order_by(ExperimentProgressRow.experiment_id.asc())
        return [_progress_from_row(r) for r in self._session.scalars(stmt)]

    def list_all_learning_records(self) -> Sequence[ProjectedLearningRecord]:
        stmt = select(LearningHistoryRow).order_by(LearningHistoryRow.learning_id.asc())
        return [_learning_from_row(r) for r in self._session.scalars(stmt)]


def _hypothesis_to_row(row: ProjectedHypothesis) -> CurrentHypothesisRow:
    return CurrentHypothesisRow(
        hypothesis_id=row.hypothesis_id,
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        domain_pack=row.domain_pack,
        template_id=row.template_id,
        template_version=row.template_version,
        statement=row.statement,
        direction=row.direction,
        causality_level=row.causality_level,
        status=row.status,
        human_confirmed=1 if row.human_confirmed else 0,
        parameters_json=dict(row.parameters) if row.parameters else None,
        proposed_at=row.proposed_at,
        activated_at=row.activated_at,
        retired_at=row.retired_at,
        experiment_id=row.experiment_id,
        audit_id=row.audit_id,
        event_id=row.event_id,
        global_position=row.global_position,
        updated_at=row.updated_at,
    )


def _hypothesis_from_row(row: CurrentHypothesisRow) -> ProjectedHypothesis:
    return ProjectedHypothesis(
        hypothesis_id=row.hypothesis_id,
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        domain_pack=row.domain_pack,
        template_id=row.template_id,
        template_version=row.template_version,
        statement=row.statement,
        direction=row.direction,
        causality_level=row.causality_level,
        status=row.status,
        human_confirmed=bool(row.human_confirmed),
        parameters=dict(row.parameters_json) if row.parameters_json else None,
        proposed_at=_as_utc(row.proposed_at),
        activated_at=_as_utc_opt(row.activated_at),
        retired_at=_as_utc_opt(row.retired_at),
        experiment_id=row.experiment_id,
        audit_id=row.audit_id,
        event_id=row.event_id,
        global_position=int(row.global_position),
        updated_at=_as_utc(row.updated_at),
    )


def _experiment_to_row(row: ProjectedExperiment) -> CurrentExperimentRow:
    return CurrentExperimentRow(
        experiment_id=row.experiment_id,
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        hypothesis_id=row.hypothesis_id,
        protocol_version=row.protocol_version,
        analysis_method=row.analysis_method,
        baseline_cutoff=row.baseline_cutoff,
        prospective_start=row.prospective_start,
        prospective_target=row.prospective_target,
        maximum_window_days=row.maximum_window_days,
        minimum_group_size=row.minimum_group_size,
        minimum_meaningful_difference=row.minimum_meaningful_difference,
        sleep_threshold_hours=row.sleep_threshold_hours,
        random_seed_policy=row.random_seed_policy,
        status=row.status,
        pre_registered_at=row.pre_registered_at,
        audit_id=row.audit_id,
        event_id=row.event_id,
        global_position=row.global_position,
        updated_at=row.updated_at,
    )


def _experiment_from_row(row: CurrentExperimentRow) -> ProjectedExperiment:
    return ProjectedExperiment(
        experiment_id=row.experiment_id,
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        hypothesis_id=row.hypothesis_id,
        protocol_version=row.protocol_version,
        analysis_method=row.analysis_method,
        baseline_cutoff=_as_utc(row.baseline_cutoff),
        prospective_start=_as_utc(row.prospective_start),
        prospective_target=row.prospective_target,
        maximum_window_days=row.maximum_window_days,
        minimum_group_size=row.minimum_group_size,
        minimum_meaningful_difference=row.minimum_meaningful_difference,
        sleep_threshold_hours=row.sleep_threshold_hours,
        random_seed_policy=row.random_seed_policy,
        status=row.status,
        pre_registered_at=_as_utc(row.pre_registered_at),
        audit_id=row.audit_id,
        event_id=row.event_id,
        global_position=int(row.global_position),
        updated_at=_as_utc(row.updated_at),
    )


def _belief_to_row(row: ProjectedBeliefSnapshot) -> BeliefSnapshotRow:
    return BeliefSnapshotRow(
        belief_id=row.belief_id,
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        hypothesis_id=row.hypothesis_id,
        evidence_id=row.evidence_id,
        previous_belief_id=row.previous_belief_id,
        belief_state=row.belief_state,
        model_probability=row.model_probability,
        credible_interval_low=row.credible_interval_low,
        credible_interval_high=row.credible_interval_high,
        estimated_effect=row.estimated_effect,
        minimum_meaningful_difference=row.minimum_meaningful_difference,
        data_confidence=row.data_confidence,
        method_confidence=row.method_confidence,
        conclusion_confidence=row.conclusion_confidence,
        recommendation_confidence=row.recommendation_confidence,
        calibration_state=row.calibration_state,
        causality_level=row.causality_level,
        limitations_json=list(row.limitations),
        is_current=1 if row.is_current else 0,
        created_at=row.created_at,
        audit_id=row.audit_id,
        event_id=row.event_id,
        global_position=row.global_position,
    )


def _belief_from_row(row: BeliefSnapshotRow) -> ProjectedBeliefSnapshot:
    return ProjectedBeliefSnapshot(
        belief_id=row.belief_id,
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        hypothesis_id=row.hypothesis_id,
        evidence_id=row.evidence_id,
        previous_belief_id=row.previous_belief_id,
        belief_state=row.belief_state,
        model_probability=row.model_probability,
        credible_interval_low=row.credible_interval_low,
        credible_interval_high=row.credible_interval_high,
        estimated_effect=row.estimated_effect,
        minimum_meaningful_difference=row.minimum_meaningful_difference,
        data_confidence=row.data_confidence,
        method_confidence=row.method_confidence,
        conclusion_confidence=row.conclusion_confidence,
        recommendation_confidence=row.recommendation_confidence,
        calibration_state=row.calibration_state,
        causality_level=row.causality_level,
        limitations=tuple(str(x) for x in row.limitations_json),
        is_current=bool(row.is_current),
        created_at=_as_utc(row.created_at),
        audit_id=row.audit_id,
        event_id=row.event_id,
        global_position=int(row.global_position),
    )


def _evidence_to_row(row: ProjectedEvidenceSnapshot) -> EvidenceSnapshotRow:
    return EvidenceSnapshotRow(
        evidence_id=row.evidence_id,
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        hypothesis_id=row.hypothesis_id,
        experiment_id=row.experiment_id,
        phase=row.phase,
        source_observation_ids=list(row.source_observation_ids),
        source_event_ids=list(row.source_event_ids),
        source_hash=row.source_hash,
        eligible_count=row.eligible_count,
        excluded_count=row.excluded_count,
        exclusion_reasons=dict(row.exclusion_reasons),
        group_counts=dict(row.group_counts),
        descriptive_statistics=dict(row.descriptive_statistics),
        analysis_parameters=dict(row.analysis_parameters),
        analysis_result=dict(row.analysis_result) if row.analysis_result else None,
        confounding_diagnostics=list(row.confounding_diagnostics),
        limitations_json=list(row.limitations),
        belief_state=row.belief_state,
        generated_at=row.generated_at,
        audit_id=row.audit_id,
        event_id=row.event_id,
        global_position=row.global_position,
    )


def _evidence_from_row(row: EvidenceSnapshotRow) -> ProjectedEvidenceSnapshot:
    return ProjectedEvidenceSnapshot(
        evidence_id=row.evidence_id,
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        hypothesis_id=row.hypothesis_id,
        experiment_id=row.experiment_id,
        phase=row.phase,
        source_observation_ids=tuple(str(x) for x in row.source_observation_ids),
        source_event_ids=tuple(str(x) for x in row.source_event_ids),
        source_hash=row.source_hash,
        eligible_count=row.eligible_count,
        excluded_count=row.excluded_count,
        exclusion_reasons={
            str(k): int(cast(Any, v))
            for k, v in cast(dict[Any, Any], row.exclusion_reasons).items()
        },
        group_counts={
            str(k): int(cast(Any, v)) for k, v in cast(dict[Any, Any], row.group_counts).items()
        },
        descriptive_statistics=dict(cast(dict[Any, Any], row.descriptive_statistics)),
        analysis_parameters=dict(cast(dict[Any, Any], row.analysis_parameters)),
        analysis_result=(
            dict(cast(dict[Any, Any], row.analysis_result)) if row.analysis_result else None
        ),
        confounding_diagnostics=tuple(
            {str(k): cast(object, v) for k, v in cast(dict[Any, Any], item).items()}
            for item in cast(list[Any], row.confounding_diagnostics)
        ),
        limitations=tuple(str(x) for x in row.limitations_json),
        belief_state=row.belief_state,
        generated_at=_as_utc(row.generated_at),
        audit_id=row.audit_id,
        event_id=row.event_id,
        global_position=int(row.global_position),
    )


def _progress_to_row(row: ProjectedExperimentProgress) -> ExperimentProgressRow:
    return ExperimentProgressRow(
        experiment_id=row.experiment_id,
        hypothesis_id=row.hypothesis_id,
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        baseline_eligible=row.baseline_eligible,
        baseline_sufficient=row.baseline_sufficient,
        baseline_below=row.baseline_below,
        prospective_eligible=row.prospective_eligible,
        prospective_sufficient=row.prospective_sufficient,
        prospective_below=row.prospective_below,
        prospective_target=row.prospective_target,
        window_days_remaining=row.window_days_remaining,
        status=row.status,
        current_belief_state=row.current_belief_state,
        last_evaluated_at=row.last_evaluated_at,
        updated_at=row.updated_at,
    )


def _progress_from_row(row: ExperimentProgressRow) -> ProjectedExperimentProgress:
    return ProjectedExperimentProgress(
        experiment_id=row.experiment_id,
        hypothesis_id=row.hypothesis_id,
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        baseline_eligible=row.baseline_eligible,
        baseline_sufficient=row.baseline_sufficient,
        baseline_below=row.baseline_below,
        prospective_eligible=row.prospective_eligible,
        prospective_sufficient=row.prospective_sufficient,
        prospective_below=row.prospective_below,
        prospective_target=row.prospective_target,
        window_days_remaining=row.window_days_remaining,
        status=row.status,
        current_belief_state=row.current_belief_state,
        last_evaluated_at=_as_utc_opt(row.last_evaluated_at),
        updated_at=_as_utc(row.updated_at),
    )


def _learning_to_row(row: ProjectedLearningRecord) -> LearningHistoryRow:
    return LearningHistoryRow(
        learning_id=row.learning_id,
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        hypothesis_id=row.hypothesis_id,
        previous_belief_id=row.previous_belief_id,
        new_belief_id=row.new_belief_id,
        outcome_evaluation_id=row.outcome_evaluation_id,
        change_type=row.change_type,
        what_changed=row.what_changed,
        why_changed=row.why_changed,
        what_remains_unknown=row.what_remains_unknown,
        next_evidence_needed=row.next_evidence_needed,
        created_at=row.created_at,
        audit_id=row.audit_id,
        event_id=row.event_id,
        global_position=row.global_position,
    )


def _learning_from_row(row: LearningHistoryRow) -> ProjectedLearningRecord:
    return ProjectedLearningRecord(
        learning_id=row.learning_id,
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        hypothesis_id=row.hypothesis_id,
        previous_belief_id=row.previous_belief_id,
        new_belief_id=row.new_belief_id,
        outcome_evaluation_id=row.outcome_evaluation_id,
        change_type=row.change_type,
        what_changed=row.what_changed,
        why_changed=row.why_changed,
        what_remains_unknown=row.what_remains_unknown,
        next_evidence_needed=row.next_evidence_needed,
        created_at=_as_utc(row.created_at),
        audit_id=row.audit_id,
        event_id=row.event_id,
        global_position=int(row.global_position),
    )
