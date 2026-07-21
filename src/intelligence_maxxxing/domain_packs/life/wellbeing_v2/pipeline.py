"""Wellbeing V2 layered pipeline (SHADOW). Deterministic; no LLM."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from intelligence_maxxxing.domain_packs.life.measurement_scale import (
    MEASUREMENT_CONTRACT_VERSION,
    NORMALIZATION_VERSION,
    ScaleExtractionReport,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.change_detection import detect_change_state
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.confidence import compose_confidence
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.features import build_features
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.happiness import compose_happiness
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.observations import (
    DayRecord,
    extract_day_records,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.registry import (
    ACCUMULATION_RETENTION,
    FORMULA_ID,
    FORMULA_STATUS,
    FORMULA_VERSION,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.stress import compose_stress


@dataclass(frozen=True)
class WellbeingV2Result:
    formula_id: str
    formula_version: str
    formula_status: str
    as_of: str
    observation_cutoff: str
    input_fingerprint: str
    happiness: dict[str, Any]
    stress: dict[str, Any]
    overall_confidence: float
    change_state: str
    contributors: list[dict[str, Any]]
    protective_factors: list[dict[str, Any]]
    data_quality: dict[str, Any]
    missing_data: list[str]
    features: dict[str, Any]
    suggested_actions: list[dict[str, Any]]
    explanation: dict[str, Any]
    sample_size: int
    missing_days: int
    period_start: str
    period_end: str
    as_of_global_position: int | None
    # Flat fields for V1-compatible snapshot storage
    happiness_score: float | None
    stress_score: float | None
    confidence_score: float | None


def _fingerprint(days: list[DayRecord], as_of: date, window: int) -> str:
    payload = {
        "as_of": as_of.isoformat(),
        "window": window,
        "days": [
            {
                "d": d.day.isoformat(),
                "h": d.happiness,
                "s": d.stress,
                "e": d.energy,
                "p": d.productivity,
                "sl": d.sleep_hours,
                "g": d.gym_done,
                "so": d.social_activity,
                "a": d.alcohol,
                "m": d.meetings_count,
                "w": d.workout_done,
                "gp": d.global_position,
            }
            for d in days
            if d.day <= as_of
        ],
        "v": FORMULA_VERSION,
    }
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def _recommendations(
    change_state: str,
    happiness: dict[str, Any],
    stress: dict[str, Any],
    confidence: float,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if confidence < 35:
        actions.append(
            {
                "id": "complete_checkin",
                "capability_class": "ANALYZE",
                "urgency": "LOW",
                "title": "Complete a short check-in to improve the estimate",
                "rationale": "Confidence is low; more structured observations reduce uncertainty.",
            }
        )
        return actions
    if change_state in {"RISING_STRESS", "PERSISTENT_LOAD"} and confidence >= 40:
        actions.append(
            {
                "id": "protect_recovery_block",
                "capability_class": "EXPLAIN",
                "urgency": "MEDIUM" if confidence >= 55 else "LOW",
                "title": "Review recovery and schedule compression",
                "rationale": "Stress trend rising with accumulated load signals in the model.",
            }
        )
    h = happiness.get("score")
    s = stress.get("score")
    if h is not None and s is not None and h < 45 and s < 45:
        actions.append(
            {
                "id": "add_enjoyable_activity",
                "capability_class": "EXPLAIN",
                "urgency": "LOW",
                "title": "Consider a small enjoyable or social activity",
                "rationale": "Happiness low with Stress also low — relaxation-only may miss understimulation.",
            }
        )
    if h is not None and s is not None and h >= 60 and s >= 65:
        actions.append(
            {
                "id": "preserve_positive_load",
                "capability_class": "EXPLAIN",
                "urgency": "LOW",
                "title": "High engagement day — protect sleep rather than cancel positives",
                "rationale": "Happiness and Stress can both be elevated; model does not force them inverse.",
            }
        )
    if not actions:
        actions.append(
            {
                "id": "maintain_observation_cadence",
                "capability_class": "ANALYZE",
                "urgency": "LOW",
                "title": "Maintain observation cadence",
                "rationale": "No high-urgency ANALYZE/EXPLAIN action from current shadow estimate.",
            }
        )
    # Never HIGH urgency below confidence threshold
    for a in actions:
        if confidence < 45 and a.get("urgency") == "MEDIUM":
            a["urgency"] = "LOW"
    return actions


def compute_wellbeing_v2(
    rows: list[Any] | list[DayRecord],
    *,
    window_days: int = 14,
    as_of: date | None = None,
    label_count: int = 0,
    scale_report: ScaleExtractionReport | None = None,
) -> WellbeingV2Result:
    report = scale_report or ScaleExtractionReport()
    if rows and isinstance(rows[0], DayRecord):
        days = list(rows)  # type: ignore[arg-type]
    else:
        days = extract_day_records(list(rows), report=report)  # type: ignore[arg-type]

    features = build_features(
        days,
        as_of=as_of,
        window_days=window_days,
        retention=ACCUMULATION_RETENTION,
    )
    happiness = compose_happiness(features)
    stress = compose_stress(features)
    conf = compose_confidence(
        features,
        happiness_score=happiness.score,
        stress_score=stress.score,
        label_count=label_count,
    )
    # Ambiguous / invalid scales must not yield high confidence.
    overall = conf.overall
    if report.ambiguous_count > 0:
        overall = min(overall, 40.0)
    if report.invalid_count > 0:
        overall = min(overall, max(25.0, overall * 0.85))
    if report.legacy_count > 0 and report.explicit_count == 0:
        overall = round(overall * 0.92, 2)
    change = detect_change_state(happiness, stress, sample_size=features.sample_size)

    h_block = {
        "score": happiness.score,
        "baseline": happiness.baseline,
        "acute": happiness.acute,
        "chronic": happiness.chronic,
        "trend": happiness.trend,
        "confidence": conf.happiness_confidence,
        "plausible_range": list(conf.plausible_happiness) if conf.plausible_happiness else None,
        "sub_scores": happiness.sub_scores,
    }
    s_block = {
        "score": stress.score,
        "baseline": stress.baseline,
        "acute": stress.acute,
        "chronic": stress.chronic,
        "anticipatory": stress.anticipatory,
        "trend": stress.trend,
        "confidence": conf.stress_confidence,
        "plausible_range": list(conf.plausible_stress) if conf.plausible_stress else None,
        "sub_scores": stress.sub_scores,
    }

    missing: list[str] = []
    for domain in ("subjective", "sleep", "schedule", "activity"):
        if domain not in features.observed_domains:
            missing.append(domain)

    max_pos = max((d.global_position for d in days if d.day <= features.as_of), default=None)
    period_start = (features.as_of - timedelta(days=window_days - 1)).isoformat()

    actions = _recommendations(change, h_block, s_block, overall)
    fp = _fingerprint(days, features.as_of, window_days)

    return WellbeingV2Result(
        formula_id=FORMULA_ID,
        formula_version=FORMULA_VERSION,
        formula_status=FORMULA_STATUS,
        as_of=features.as_of.isoformat(),
        observation_cutoff=features.as_of.isoformat() + "T23:59:59",
        input_fingerprint=fp,
        happiness=h_block,
        stress=s_block,
        overall_confidence=overall,
        change_state=change,
        contributors=happiness.contributors[:4] + stress.contributors[:4],
        protective_factors=stress.protective_factors,
        data_quality={
            "sample_size": features.sample_size,
            "missing_days": features.missing_days,
            "maturity": features.maturity,
            "confidence_components": conf.components,
            "calibration_status": conf.calibration_status,
        },
        missing_data=missing,
        features={
            "signals": {k: v for k, v in features.signals.items()},
            "baselines": features.baselines,
            "load_state": features.load_state,
            "sleep_debt_3d": features.sleep_debt_3d,
            **report.as_features(),
        },
        suggested_actions=actions,
        explanation={
            "summary": (
                f"Wellbeing V2 SHADOW estimate for {features.as_of.isoformat()} "
                f"({features.sample_size} days in window)."
            ),
            "happiness_definition": "Hierarchical sub-scores; not productivity; not 100-stress.",
            "stress_definition": "Acute/chronic/anticipatory load with accumulation retention 0.72.",
            "confidence_definition": conf.explanation,
            "autonomy": "ANALYZE/EXPLAIN only; suggested_actions are not RECOMMEND capability.",
            "formula_status": FORMULA_STATUS,
            "non_clinical": True,
            "measurement_contract_version": MEASUREMENT_CONTRACT_VERSION,
            "input_normalization_version": NORMALIZATION_VERSION,
            "input_scale_policy": (
                "Canonical 0–100 inputs from explicit scale or known legacy adapter; "
                "no magnitude inference."
            ),
        },
        sample_size=features.sample_size,
        missing_days=features.missing_days,
        period_start=period_start,
        period_end=features.as_of.isoformat(),
        as_of_global_position=max_pos,
        happiness_score=happiness.score,
        stress_score=stress.score,
        confidence_score=overall,
    )


def result_to_dict(result: WellbeingV2Result) -> dict[str, Any]:
    return asdict(result)
