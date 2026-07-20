"""Wellbeing Intelligence V1 use cases (ANALYZE / EXPLAIN)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from intelligence_maxxxing.application.auth import AuthContext
from intelligence_maxxxing.application.ports import UnitOfWorkPort
from intelligence_maxxxing.contracts.api.wellbeing.models import (
    WellbeingFeedbackResult,
    WellbeingFormulaData,
    WellbeingSnapshotView,
)
from intelligence_maxxxing.domain.common.identifiers import new_id
from intelligence_maxxxing.domain_packs.life.observation_scan import scan_all_life_observations
from intelligence_maxxxing.domain_packs.life.wellbeing_v1 import (
    FORMULA_ID,
    FORMULA_VERSION,
    compute_wellbeing_v1,
    extract_checkin_days,
)
from intelligence_maxxxing.infrastructure.database.tables import (
    WellbeingBaselineRow,
    WellbeingFeatureSnapshotRow,
    WellbeingFeedbackRow,
    WellbeingFormulaVersionRow,
    WellbeingScoreSnapshotRow,
)

FORMULA_DESCRIPTION = (
    "Deterministic Happiness / Stress / Confidence from life daily check-ins. "
    "Happiness is not 100 minus stress; Confidence is independent. "
    "suggested_actions are ANALYZE/EXPLAIN candidates, not RECOMMEND."
)


def _ensure_formula_row(session: Session) -> None:
    row = session.execute(
        select(WellbeingFormulaVersionRow).where(
            WellbeingFormulaVersionRow.formula_id == FORMULA_ID,
            WellbeingFormulaVersionRow.version == FORMULA_VERSION,
        )
    ).scalar_one_or_none()
    if row is not None:
        return
    session.add(
        WellbeingFormulaVersionRow(
            formula_id=FORMULA_ID,
            version=FORMULA_VERSION,
            description=FORMULA_DESCRIPTION,
            active=1,
            created_at=datetime.now(UTC),
        )
    )


def _result_to_view(
    *,
    score_id: str,
    result: Any,
    computed_at: datetime,
) -> WellbeingSnapshotView:
    return WellbeingSnapshotView(
        score_snapshot_id=score_id,
        formula_id=result.formula_id,
        formula_version=result.formula_version,
        happiness=result.happiness,
        stress=result.stress,
        confidence=result.confidence,
        early_warning=str(result.early_warning),
        data_sufficiency=str(result.data_sufficiency),
        sample_size=result.sample_size,
        missing_days=result.missing_days,
        period_start=result.period_start,
        period_end=result.period_end,
        features=result.features,
        contributors=result.contributors,
        suggested_actions=result.suggested_actions,
        explanation=result.explanation,
        baselines=result.baselines,
        computed_at=computed_at.isoformat(),
        as_of_global_position=result.as_of_global_position,
    )


class WellbeingService:
    """Compute + persist wellbeing snapshots for the authenticated scope."""

    def __init__(
        self,
        uow: UnitOfWorkPort,
        session_factory: sessionmaker[Session],
    ) -> None:
        self._uow = uow
        self._session_factory = session_factory

    def get_current(self, auth: AuthContext, *, window_days: int = 14) -> WellbeingSnapshotView:
        with self._uow as uow:
            rows = scan_all_life_observations(
                uow.projections,
                owner_id=auth.owner_id,
                application_id=auth.application_id,
            )
            uow.commit()

        days = extract_checkin_days(list(rows))
        result = compute_wellbeing_v1(days, window_days=window_days)
        now = datetime.now(UTC)
        score_id = new_id("wbs")
        feature_id = new_id("wbf")

        with self._session_factory() as session:
            _ensure_formula_row(session)
            session.add(
                WellbeingFeatureSnapshotRow(
                    feature_snapshot_id=feature_id,
                    tenant_id=auth.tenant_id,
                    owner_id=auth.owner_id,
                    application_id=auth.application_id,
                    formula_id=result.formula_id,
                    formula_version=result.formula_version,
                    period_start=result.period_start,
                    period_end=result.period_end,
                    features_json=result.features,
                    sample_size=result.sample_size,
                    missing_days=result.missing_days,
                    computed_at=now,
                    as_of_global_position=result.as_of_global_position,
                )
            )
            session.add(
                WellbeingScoreSnapshotRow(
                    score_snapshot_id=score_id,
                    tenant_id=auth.tenant_id,
                    owner_id=auth.owner_id,
                    application_id=auth.application_id,
                    formula_id=result.formula_id,
                    formula_version=result.formula_version,
                    feature_snapshot_id=feature_id,
                    happiness=result.happiness,
                    stress=result.stress,
                    confidence=result.confidence,
                    early_warning=str(result.early_warning),
                    data_sufficiency=str(result.data_sufficiency),
                    contributors_json=result.contributors,
                    suggested_actions_json=result.suggested_actions,
                    explanation_json=result.explanation,
                    computed_at=now,
                    as_of_global_position=result.as_of_global_position,
                )
            )
            for window, features in result.baselines.items():
                session.add(
                    WellbeingBaselineRow(
                        baseline_id=new_id("wbb"),
                        tenant_id=auth.tenant_id,
                        owner_id=auth.owner_id,
                        application_id=auth.application_id,
                        window_days=int(window),
                        formula_id=result.formula_id,
                        formula_version=result.formula_version,
                        features_json=features,
                        sample_size=int(features.get("sample_size") or 0),
                        computed_at=now,
                        as_of_global_position=result.as_of_global_position,
                    )
                )
            session.commit()

        return _result_to_view(score_id=score_id, result=result, computed_at=now)

    def list_history(self, auth: AuthContext, *, limit: int = 20) -> list[WellbeingSnapshotView]:
        with self._session_factory() as session:
            rows = session.execute(
                select(WellbeingScoreSnapshotRow)
                .where(
                    WellbeingScoreSnapshotRow.tenant_id == auth.tenant_id,
                    WellbeingScoreSnapshotRow.owner_id == auth.owner_id,
                    WellbeingScoreSnapshotRow.application_id == auth.application_id,
                )
                .order_by(WellbeingScoreSnapshotRow.computed_at.desc())
                .limit(limit)
            ).scalars().all()
            views: list[WellbeingSnapshotView] = []
            for row in rows:
                feat = None
                if row.feature_snapshot_id:
                    feat = session.get(WellbeingFeatureSnapshotRow, row.feature_snapshot_id)
                views.append(
                    WellbeingSnapshotView(
                        score_snapshot_id=row.score_snapshot_id,
                        formula_id=row.formula_id,
                        formula_version=row.formula_version,
                        happiness=row.happiness,
                        stress=row.stress,
                        confidence=row.confidence,
                        early_warning=row.early_warning,
                        data_sufficiency=row.data_sufficiency,
                        sample_size=feat.sample_size if feat else 0,
                        missing_days=feat.missing_days if feat else 0,
                        period_start=feat.period_start if feat else "",
                        period_end=feat.period_end if feat else "",
                        features=feat.features_json if feat else {},
                        contributors=list(row.contributors_json or []),
                        suggested_actions=list(row.suggested_actions_json or []),
                        explanation=dict(row.explanation_json or {}),
                        baselines={},
                        computed_at=row.computed_at.isoformat(),
                        as_of_global_position=row.as_of_global_position,
                    )
                )
            return views

    def get_explanation(self, auth: AuthContext, score_snapshot_id: str | None = None) -> WellbeingSnapshotView:
        if score_snapshot_id:
            with self._session_factory() as session:
                row = session.get(WellbeingScoreSnapshotRow, score_snapshot_id)
                if (
                    row is not None
                    and row.tenant_id == auth.tenant_id
                    and row.owner_id == auth.owner_id
                    and row.application_id == auth.application_id
                ):
                    feat = (
                        session.get(WellbeingFeatureSnapshotRow, row.feature_snapshot_id)
                        if row.feature_snapshot_id
                        else None
                    )
                    return WellbeingSnapshotView(
                        score_snapshot_id=row.score_snapshot_id,
                        formula_id=row.formula_id,
                        formula_version=row.formula_version,
                        happiness=row.happiness,
                        stress=row.stress,
                        confidence=row.confidence,
                        early_warning=row.early_warning,
                        data_sufficiency=row.data_sufficiency,
                        sample_size=feat.sample_size if feat else 0,
                        missing_days=feat.missing_days if feat else 0,
                        period_start=feat.period_start if feat else "",
                        period_end=feat.period_end if feat else "",
                        features=feat.features_json if feat else {},
                        contributors=list(row.contributors_json or []),
                        suggested_actions=list(row.suggested_actions_json or []),
                        explanation=dict(row.explanation_json or {}),
                        baselines={},
                        computed_at=row.computed_at.isoformat(),
                        as_of_global_position=row.as_of_global_position,
                    )
        return self.get_current(auth)

    def get_formula(self) -> WellbeingFormulaData:
        with self._session_factory() as session:
            _ensure_formula_row(session)
            session.commit()
        return WellbeingFormulaData(
            formula_id=FORMULA_ID,
            version=FORMULA_VERSION,
            description=FORMULA_DESCRIPTION,
            active=True,
            happiness_neq_100_minus_stress=True,
        )

    def submit_feedback(
        self,
        auth: AuthContext,
        *,
        rating: str,
        score_snapshot_id: str | None,
        note: str | None,
    ) -> WellbeingFeedbackResult:
        feedback_id = new_id("wbfd")
        with self._session_factory() as session:
            session.add(
                WellbeingFeedbackRow(
                    feedback_id=feedback_id,
                    tenant_id=auth.tenant_id,
                    owner_id=auth.owner_id,
                    application_id=auth.application_id,
                    score_snapshot_id=score_snapshot_id,
                    rating=rating,
                    note=note,
                    created_at=datetime.now(UTC),
                )
            )
            session.commit()
        return WellbeingFeedbackResult(feedback_id=feedback_id, accepted=True)
