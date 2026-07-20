"""Wellbeing Intelligence use cases — V1 ACTIVE + V2 SHADOW."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from intelligence_maxxxing.application.auth import AuthContext
from intelligence_maxxxing.application.ports import UnitOfWorkPort
from intelligence_maxxxing.contracts.api.wellbeing.models import (
    ScoreBlockView,
    WellbeingFeedbackResult,
    WellbeingFormulaData,
    WellbeingShadowCompareData,
    WellbeingSnapshotView,
)
from intelligence_maxxxing.domain.common.identifiers import new_id
from intelligence_maxxxing.domain_packs.life.observation_scan import scan_all_life_observations
from intelligence_maxxxing.domain_packs.life.wellbeing_v1 import (
    FORMULA_ID as V1_ID,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v1 import (
    FORMULA_VERSION as V1_VERSION,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v1 import (
    compute_wellbeing_v1,
    extract_checkin_days,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.pipeline import compute_wellbeing_v2
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.registry import (
    FORMULA_ID as V2_ID,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.registry import (
    FORMULA_STATUS as V2_STATUS,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.registry import (
    FORMULA_VERSION as V2_VERSION,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.registry import (
    HAPPINESS_WEIGHTS,
    STRESS_WEIGHTS,
    WEIGHTS,
)
from intelligence_maxxxing.infrastructure.database.tables import (
    WellbeingBaselineRow,
    WellbeingFeatureSnapshotRow,
    WellbeingFeedbackRow,
    WellbeingFormulaVersionRow,
    WellbeingScoreSnapshotRow,
)

V1_DESCRIPTION = (
    "Deterministic Happiness / Stress / Confidence from life daily check-ins. "
    "Happiness is not 100 minus stress; Confidence is independent. "
    "suggested_actions are ANALYZE/EXPLAIN candidates, not RECOMMEND."
)
V2_DESCRIPTION = (
    "Advanced personal wellbeing state model V2 (SHADOW). Hierarchical Happiness "
    "and Stress Load with accumulation, multi-component Confidence, attribution, "
    "and change detection. Does not replace V1 until promotion gates pass."
)


def _ensure_formula_rows(session: Session) -> None:
    for fid, ver, desc, active, status in (
        (V1_ID, V1_VERSION, V1_DESCRIPTION, 1, "ACTIVE"),
        (V2_ID, V2_VERSION, V2_DESCRIPTION, 0, V2_STATUS),
    ):
        row = session.execute(
            select(WellbeingFormulaVersionRow).where(
                WellbeingFormulaVersionRow.formula_id == fid,
                WellbeingFormulaVersionRow.version == ver,
            )
        ).scalar_one_or_none()
        if row is None:
            session.add(
                WellbeingFormulaVersionRow(
                    formula_id=fid,
                    version=ver,
                    description=desc,
                    active=active,
                    created_at=datetime.now(UTC),
                    status=status,
                )
            )
        elif getattr(row, "status", None) is None:
            row.status = status


def _v1_to_view(score_id: str, result: Any, computed_at: datetime) -> WellbeingSnapshotView:
    return WellbeingSnapshotView(
        score_snapshot_id=score_id,
        formula_id=result.formula_id,
        formula_version=result.formula_version,
        formula_status="ACTIVE",
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
        overall_confidence=result.confidence,
    )


def _v2_to_view(score_id: str, result: Any, computed_at: datetime) -> WellbeingSnapshotView:
    early = result.change_state if result.change_state != "STABLE" else "NONE"
    sufficiency = "COLD_START" if result.sample_size < 3 else ("PARTIAL" if result.missing_days > 7 else "ADEQUATE")
    return WellbeingSnapshotView(
        score_snapshot_id=score_id,
        formula_id=result.formula_id,
        formula_version=result.formula_version,
        formula_status=result.formula_status,
        happiness=result.happiness_score,
        stress=result.stress_score,
        confidence=result.confidence_score,
        early_warning=early,
        data_sufficiency=sufficiency,
        sample_size=result.sample_size,
        missing_days=result.missing_days,
        period_start=result.period_start,
        period_end=result.period_end,
        features=result.features,
        contributors=result.contributors,
        suggested_actions=result.suggested_actions,
        explanation=result.explanation,
        baselines=result.features.get("baselines") or {},
        computed_at=computed_at.isoformat(),
        as_of_global_position=result.as_of_global_position,
        happiness_block=ScoreBlockView(**{k: v for k, v in result.happiness.items() if k in ScoreBlockView.model_fields}),
        stress_block=ScoreBlockView(**{k: v for k, v in result.stress.items() if k in ScoreBlockView.model_fields}),
        overall_confidence=result.overall_confidence,
        change_state=result.change_state,
        protective_factors=result.protective_factors,
        missing_data=result.missing_data,
        data_quality=result.data_quality,
        input_fingerprint=result.input_fingerprint,
        as_of=result.as_of,
        observation_cutoff=result.observation_cutoff,
    )


class WellbeingService:
    """Compute + persist wellbeing snapshots. Default formula = V1 ACTIVE."""

    def __init__(
        self,
        uow: UnitOfWorkPort,
        session_factory: sessionmaker[Session],
    ) -> None:
        self._uow = uow
        self._session_factory = session_factory

    def _scan(self, auth: AuthContext) -> list[Any]:
        with self._uow as uow:
            rows = scan_all_life_observations(
                uow.projections,
                owner_id=auth.owner_id,
                application_id=auth.application_id,
            )
            uow.commit()
        return list(rows)

    def get_current(
        self,
        auth: AuthContext,
        *,
        window_days: int = 14,
        formula_id: str = V1_ID,
    ) -> WellbeingSnapshotView:
        rows = self._scan(auth)
        now = datetime.now(UTC)
        score_id = new_id("wbs")
        feature_id = new_id("wbf")

        if formula_id == V2_ID:
            result = compute_wellbeing_v2(rows, window_days=window_days)
            view = _v2_to_view(score_id, result, now)
            early = view.early_warning
            sufficiency = view.data_sufficiency
            features_json = result.features
            contributors = result.contributors
            actions = result.suggested_actions
            explanation = result.explanation
            happiness = result.happiness_score
            stress = result.stress_score
            confidence = result.confidence_score
            period_start = result.period_start
            period_end = result.period_end
            sample = result.sample_size
            missing = result.missing_days
            as_of_pos = result.as_of_global_position
            v2_fields = dict(
                formula_status=result.formula_status,
                input_fingerprint=result.input_fingerprint,
                change_state=result.change_state,
                happiness_confidence=result.happiness.get("confidence"),
                stress_confidence=result.stress.get("confidence"),
                overall_confidence=result.overall_confidence,
                sub_scores_json={
                    "happiness": result.happiness.get("sub_scores"),
                    "stress": result.stress.get("sub_scores"),
                },
                plausible_range_json={
                    "happiness": result.happiness.get("plausible_range"),
                    "stress": result.stress.get("plausible_range"),
                },
                happiness_acute=result.happiness.get("acute"),
                happiness_chronic=result.happiness.get("chronic"),
                stress_acute=result.stress.get("acute"),
                stress_chronic=result.stress.get("chronic"),
                stress_anticipatory=result.stress.get("anticipatory"),
            )
            fid, fver = V2_ID, V2_VERSION
        else:
            days = extract_checkin_days(rows)
            result = compute_wellbeing_v1(days, window_days=window_days)
            view = _v1_to_view(score_id, result, now)
            early = str(result.early_warning)
            sufficiency = str(result.data_sufficiency)
            features_json = result.features
            contributors = result.contributors
            actions = result.suggested_actions
            explanation = result.explanation
            happiness = result.happiness
            stress = result.stress
            confidence = result.confidence
            period_start = result.period_start
            period_end = result.period_end
            sample = result.sample_size
            missing = result.missing_days
            as_of_pos = result.as_of_global_position
            v2_fields = {}
            fid, fver = result.formula_id, result.formula_version
            # baselines only for v1 path below
            v1_baselines = result.baselines

        with self._session_factory() as session:
            _ensure_formula_rows(session)
            session.add(
                WellbeingFeatureSnapshotRow(
                    feature_snapshot_id=feature_id,
                    tenant_id=auth.tenant_id,
                    owner_id=auth.owner_id,
                    application_id=auth.application_id,
                    formula_id=fid,
                    formula_version=fver,
                    period_start=period_start,
                    period_end=period_end,
                    features_json=features_json,
                    sample_size=sample,
                    missing_days=missing,
                    computed_at=now,
                    as_of_global_position=as_of_pos,
                )
            )
            session.add(
                WellbeingScoreSnapshotRow(
                    score_snapshot_id=score_id,
                    tenant_id=auth.tenant_id,
                    owner_id=auth.owner_id,
                    application_id=auth.application_id,
                    formula_id=fid,
                    formula_version=fver,
                    feature_snapshot_id=feature_id,
                    happiness=happiness,
                    stress=stress,
                    confidence=confidence,
                    early_warning=early,
                    data_sufficiency=sufficiency,
                    contributors_json=contributors,
                    suggested_actions_json=actions,
                    explanation_json=explanation,
                    computed_at=now,
                    as_of_global_position=as_of_pos,
                    **v2_fields,
                )
            )
            if formula_id != V2_ID:
                for window, feats in v1_baselines.items():
                    session.add(
                        WellbeingBaselineRow(
                            baseline_id=new_id("wbb"),
                            tenant_id=auth.tenant_id,
                            owner_id=auth.owner_id,
                            application_id=auth.application_id,
                            window_days=int(window),
                            formula_id=fid,
                            formula_version=fver,
                            features_json=feats,
                            sample_size=int(feats.get("sample_size") or 0),
                            computed_at=now,
                            as_of_global_position=as_of_pos,
                        )
                    )
            session.commit()
        return view

    def compare_shadow(self, auth: AuthContext, *, window_days: int = 14) -> WellbeingShadowCompareData:
        v1 = self.get_current(auth, window_days=window_days, formula_id=V1_ID)
        v2 = self.get_current(auth, window_days=window_days, formula_id=V2_ID)
        div: dict[str, Any] = {}
        if v1.happiness is not None and v2.happiness is not None:
            div["happiness_delta"] = round(v2.happiness - v1.happiness, 2)
        if v1.stress is not None and v2.stress is not None:
            div["stress_delta"] = round(v2.stress - v1.stress, 2)
        if v1.confidence is not None and v2.confidence is not None:
            div["confidence_delta"] = round(v2.confidence - v1.confidence, 2)
        div["v2_change_state"] = v2.change_state
        div["v2_status"] = V2_STATUS
        return WellbeingShadowCompareData(v1=v1, v2=v2, divergences=div)

    def list_history(self, auth: AuthContext, *, limit: int = 20) -> list[WellbeingSnapshotView]:
        with self._session_factory() as session:
            rows = (
                session.execute(
                    select(WellbeingScoreSnapshotRow)
                    .where(
                        WellbeingScoreSnapshotRow.tenant_id == auth.tenant_id,
                        WellbeingScoreSnapshotRow.owner_id == auth.owner_id,
                        WellbeingScoreSnapshotRow.application_id == auth.application_id,
                    )
                    .order_by(WellbeingScoreSnapshotRow.computed_at.desc())
                    .limit(limit)
                )
                .scalars()
                .all()
            )
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
                        formula_status=getattr(row, "formula_status", None),
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
                        overall_confidence=getattr(row, "overall_confidence", None),
                        change_state=getattr(row, "change_state", None),
                        input_fingerprint=getattr(row, "input_fingerprint", None),
                    )
                )
            return views

    def get_explanation(
        self, auth: AuthContext, score_snapshot_id: str | None = None, formula_id: str = V1_ID
    ) -> WellbeingSnapshotView:
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
                        formula_status=getattr(row, "formula_status", None),
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
                        overall_confidence=getattr(row, "overall_confidence", None),
                        change_state=getattr(row, "change_state", None),
                        input_fingerprint=getattr(row, "input_fingerprint", None),
                    )
        return self.get_current(auth, formula_id=formula_id)

    def get_formula(self, formula_id: str = V1_ID) -> WellbeingFormulaData:
        with self._session_factory() as session:
            _ensure_formula_rows(session)
            session.commit()
        if formula_id == V2_ID:
            return WellbeingFormulaData(
                formula_id=V2_ID,
                version=V2_VERSION,
                description=V2_DESCRIPTION,
                active=False,
                status=V2_STATUS,
                happiness_neq_100_minus_stress=True,
                weights={
                    "happiness": dict(HAPPINESS_WEIGHTS),
                    "stress": dict(STRESS_WEIGHTS),
                    "confidence": dict(WEIGHTS.confidence),
                },
            )
        return WellbeingFormulaData(
            formula_id=V1_ID,
            version=V1_VERSION,
            description=V1_DESCRIPTION,
            active=True,
            status="ACTIVE",
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
