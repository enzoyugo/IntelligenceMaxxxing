"""Deterministic Wellbeing Intelligence V1 formulas (ANALYZE / EXPLAIN).

Life pack autonomy forbids RECOMMEND. `suggested_actions` are explanatory
action candidates under ANALYZE/EXPLAIN — not pack capability RECOMMEND.

Happiness is NOT defined as (100 - Stress). Confidence is a separate score.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from statistics import mean
from typing import Any

from intelligence_maxxxing.domain_packs.life.exclusion_registry import exclusion_id_set
from intelligence_maxxxing.domain_packs.life.input_selection import (
    SelectionReport,
    select_effective_observations,
)
from intelligence_maxxxing.domain_packs.life.measurement_scale import (
    MEASUREMENT_CONTRACT_VERSION,
    NORMALIZATION_VERSION,
    ScaleExtractionReport,
    resolve_score_fields,
)

FORMULA_ID = "wellbeing_v1"
FORMULA_VERSION = "1.2"
LIFE_EVENT_TYPE = "life.daily_check_in.completed.v1"

COLD_START_MIN_DAYS = 3
BASELINE_WINDOWS = (7, 30, 90)


class EarlyWarning(StrEnum):
    NONE = "NONE"
    ELEVATED_STRESS = "ELEVATED_STRESS"
    LOW_HAPPINESS = "LOW_HAPPINESS"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    COMPOUND_RISK = "COMPOUND_RISK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    EXTREME_SCORE_LOW_EVIDENCE = "EXTREME_SCORE_LOW_EVIDENCE"


class DataSufficiency(StrEnum):
    COLD_START = "COLD_START"
    PARTIAL = "PARTIAL"
    ADEQUATE = "ADEQUATE"
    RICH = "RICH"


@dataclass(frozen=True)
class CheckInDay:
    day: date
    happiness: float | None
    stress: float | None
    energy: float | None
    productivity: float | None
    sleep_hours: float | None
    gym_done: bool | None
    social_activity: bool | None
    alcohol: bool | None
    global_position: int


@dataclass(frozen=True)
class WellbeingResult:
    formula_id: str
    formula_version: str
    happiness: float | None
    stress: float | None
    confidence: float | None
    early_warning: EarlyWarning
    data_sufficiency: DataSufficiency
    sample_size: int
    missing_days: int
    period_start: str
    period_end: str
    features: dict[str, Any]
    contributors: list[dict[str, Any]]
    suggested_actions: list[dict[str, Any]]
    explanation: dict[str, Any]
    as_of_global_position: int | None
    baselines: dict[str, dict[str, Any]]


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _sample_maturity_cap(sample: int) -> float:
    """Hard ceiling on epistemic confidence from sample size alone."""
    if sample <= 2:
        return 25.0
    if sample <= 6:
        return 45.0
    if sample <= 13:
        return 60.0
    if sample <= 29:
        return 75.0
    return 100.0


def _is_extreme(score: float | None) -> bool:
    if score is None:
        return False
    return score <= 5.0 or score >= 95.0


def extract_checkin_days(
    rows: list[Any],
    *,
    report: ScaleExtractionReport | None = None,
    selection_report: SelectionReport | None = None,
) -> list[CheckInDay]:
    """Extract daily check-ins; score fields stored as canonical 0–100.

    Applies wellbeing_input_selection_v1 before first-write-wins so tests cannot
    capture a calendar day ahead of personal observations.
    """
    by_day: dict[date, CheckInDay] = {}
    scale_report = report or ScaleExtractionReport()
    effective, sel = select_effective_observations(rows, exclusion_ids=exclusion_id_set())
    if selection_report is not None:
        selection_report.included = sel.included
        selection_report.decisions = sel.decisions
    ordered = sorted(
        effective,
        key=lambda r: (int(getattr(r, "global_position", 0)), getattr(r, "observation_id", "")),
    )
    for row in ordered:
        if getattr(row, "domain_pack", None) != "life":
            continue
        if getattr(row, "subject", None) != "daily_check_in":
            continue
        meta = row.metadata if isinstance(getattr(row, "metadata", None), dict) else {}
        if meta.get("life_event_type") != LIFE_EVENT_TYPE:
            continue
        occurred = getattr(row, "occurred_at", None)
        if occurred is None:
            continue
        if isinstance(occurred, datetime):
            day = occurred.date()
        else:
            continue
        ctx = row.context if isinstance(getattr(row, "context", None), dict) else {}
        attrs = ctx.get("attributes") if isinstance(ctx.get("attributes"), dict) else {}
        source_ids = list(getattr(row, "source_ids", None) or [])

        def _f(key: str) -> float | None:
            raw = attrs.get(key)
            if raw is None:
                return None
            try:
                return float(raw)
            except (TypeError, ValueError):
                return None

        def _b(key: str) -> bool | None:
            raw = attrs.get(key)
            if raw is None:
                return None
            if isinstance(raw, bool):
                return raw
            if isinstance(raw, (int, float)):
                return bool(raw)
            if isinstance(raw, str):
                return raw.lower() in {"1", "true", "yes"}
            return None

        # First-write wins (lowest global_position) for a calendar day.
        if day in by_day:
            continue
        scores = resolve_score_fields(
            attrs,
            event_type=LIFE_EVENT_TYPE,
            source_ids=source_ids,
            metadata=meta,
            report=scale_report,
        )
        by_day[day] = CheckInDay(
            day=day,
            happiness=scores["happiness"],
            stress=scores["stress"],
            energy=scores["energy"],
            productivity=scores["productivity"],
            sleep_hours=_f("sleep_hours"),
            gym_done=_b("gym_done"),
            social_activity=_b("social_activity"),
            alcohol=_b("alcohol"),
            global_position=int(getattr(row, "global_position", 0)),
        )
    return sorted(by_day.values(), key=lambda d: d.day)


def _avg(values: list[float]) -> float | None:
    return mean(values) if values else None


def _baseline_features(days: list[CheckInDay], window: int, as_of: date) -> dict[str, Any]:
    start = as_of - timedelta(days=window - 1)
    window_days = [d for d in days if start <= d.day <= as_of]
    happ = [d.happiness for d in window_days if d.happiness is not None]
    stress = [d.stress for d in window_days if d.stress is not None]
    energy = [d.energy for d in window_days if d.energy is not None]
    sleep = [d.sleep_hours for d in window_days if d.sleep_hours is not None]
    return {
        "window_days": window,
        "sample_size": len(window_days),
        "avg_happiness_raw": _avg(happ),
        "avg_stress_raw": _avg(stress),
        "avg_energy_raw": _avg(energy),
        "avg_sleep_hours": _avg(sleep),
    }


def compute_wellbeing_v1(
    days: list[CheckInDay],
    *,
    window_days: int = 14,
    as_of: date | None = None,
    scale_report: ScaleExtractionReport | None = None,
) -> WellbeingResult:
    """Compute Happiness / Stress / Confidence for a trailing window.

    Score fields on CheckInDay must already be canonical 0–100 (normalized once
    in extract_checkin_days / measurement_scale). No magnitude inference here.
    """
    if as_of is None:
        as_of = max((d.day for d in days), default=date.today())
    start = as_of - timedelta(days=window_days - 1)
    window = [d for d in days if start <= d.day <= as_of]
    present_days = {d.day for d in window}
    expected = {start + timedelta(days=i) for i in range(window_days)}
    missing = len(expected - present_days)
    sample = len(window)

    max_pos = max((d.global_position for d in window), default=None)
    report = scale_report or ScaleExtractionReport()

    if sample == 0:
        return WellbeingResult(
            formula_id=FORMULA_ID,
            formula_version=FORMULA_VERSION,
            happiness=None,
            stress=None,
            confidence=None,
            early_warning=EarlyWarning.INSUFFICIENT_DATA,
            data_sufficiency=DataSufficiency.COLD_START,
            sample_size=0,
            missing_days=window_days,
            period_start=start.isoformat(),
            period_end=as_of.isoformat(),
            features={"window_days": window_days, **report.as_features()},
            contributors=[],
            suggested_actions=[
                {
                    "id": "log_checkins",
                    "capability_class": "ANALYZE",
                    "title": "Log daily check-ins",
                    "rationale": "No eligible check-in observations in the analysis window.",
                }
            ],
            explanation={
                "summary": "Insufficient data to compute wellbeing scores.",
                "happiness_note": "Happiness is not defined as 100 minus stress.",
                "cold_start_policy": f"Need at least {COLD_START_MIN_DAYS} days with scores.",
            },
            as_of_global_position=max_pos,
            baselines={},
        )

    # Already canonical 0–100 from measurement_scale.resolve_score_fields.
    happ_raw = [d.happiness for d in window if d.happiness is not None]
    stress_raw = [d.stress for d in window if d.stress is not None]
    energy_raw = [d.energy for d in window if d.energy is not None]
    prod_raw = [d.productivity for d in window if d.productivity is not None]
    sleep_raw = [d.sleep_hours for d in window if d.sleep_hours is not None]
    gym_flags = [1.0 if d.gym_done else 0.0 for d in window if d.gym_done is not None]
    alcohol_flags = [1.0 if d.alcohol else 0.0 for d in window if d.alcohol is not None]

    avg_happ = _avg(happ_raw)
    avg_stress = _avg(stress_raw)
    avg_energy = _avg(energy_raw)
    avg_prod = _avg(prod_raw)
    avg_sleep = _avg(sleep_raw)
    gym_rate = _avg(gym_flags)
    alcohol_rate = _avg(alcohol_flags) or 0.0

    happ_n = avg_happ
    stress_n = avg_stress
    energy_n = avg_energy
    prod_n = avg_prod

    # Happiness (0-100): independent composite — NOT (100 - stress). Clamp once at end.
    happiness: float | None = None
    happ_pre_clamp: float | None = None
    if happ_n is not None:
        energy_boost = ((energy_n - 50.0) * 0.15) if energy_n is not None else 0.0
        sleep_boost = 0.0
        if avg_sleep is not None:
            sleep_boost = _clamp(100.0 - abs(avg_sleep - 7.5) * 12.0, 0.0, 100.0) * 0.10 - 5.0
        happ_pre_clamp = happ_n + energy_boost + sleep_boost
        happiness = round(_clamp(happ_pre_clamp), 2)

    # Stress (0-100): higher is worse; alcohol/low sleep amplify.
    stress: float | None = None
    stress_pre_clamp: float | None = None
    if stress_n is not None:
        amp = alcohol_rate * 8.0
        if avg_sleep is not None and avg_sleep < 6.0:
            amp += (6.0 - avg_sleep) * 4.0
        stress_pre_clamp = stress_n + amp
        stress = round(_clamp(stress_pre_clamp), 2)

    # Agency score (0-100): productivity/energy/gym — kept in features, not UI confidence.
    agency_score: float | None = None
    if prod_n is not None or energy_n is not None:
        prod_c = prod_n if prod_n is not None else 50.0
        energy_c = energy_n if energy_n is not None else 50.0
        gym_c = (gym_rate * 100.0) if gym_rate is not None else 40.0
        stability = 100.0
        if len(energy_raw) >= 2:
            e_mean = mean(energy_raw)
            variance = mean([(e - e_mean) ** 2 for e in energy_raw])
            # Coefficient tuned for 0–100 units (was *8 for 1–10 Likert).
            stability = _clamp(100.0 - variance * 0.08)
        agency_score = round(
            _clamp(0.45 * prod_c + 0.30 * energy_c + 0.15 * gym_c + 0.10 * stability), 2
        )

    if sample < COLD_START_MIN_DAYS:
        sufficiency = DataSufficiency.COLD_START
    elif missing > window_days // 2:
        sufficiency = DataSufficiency.PARTIAL
    elif sample >= 10 and missing <= 2:
        sufficiency = DataSufficiency.RICH
    else:
        sufficiency = DataSufficiency.ADEQUATE

    # Epistemic confidence (what clients display as Confidence): maturity + coverage.
    domain_flags = [
        avg_happ is not None,
        avg_stress is not None,
        avg_energy is not None,
        avg_prod is not None,
        avg_sleep is not None,
        gym_rate is not None,
    ]
    domain_coverage = sum(1 for f in domain_flags if f) / float(len(domain_flags))
    day_coverage = sample / float(window_days)
    sufficiency_factor = {
        DataSufficiency.COLD_START: 0.25,
        DataSufficiency.PARTIAL: 0.45,
        DataSufficiency.ADEQUATE: 0.75,
        DataSufficiency.RICH: 1.0,
    }[sufficiency]
    # No human feedback calibration in V1.1 → uncalibrated dampener.
    calibration_status = "uncalibrated"
    calibration_factor = 0.85
    epistemic_raw = 100.0 * (
        0.45 * day_coverage + 0.35 * domain_coverage + 0.20 * sufficiency_factor
    )
    epistemic_raw *= calibration_factor
    # Penalize non-explicit / ambiguous / invalid scale resolution.
    scale_penalty = 1.0
    if report.legacy_count > 0:
        scale_penalty *= 0.92
    if report.ambiguous_count > 0:
        scale_penalty *= max(0.55, 1.0 - 0.12 * report.ambiguous_count)
    if report.invalid_count > 0:
        scale_penalty *= max(0.50, 1.0 - 0.10 * report.invalid_count)
    epistemic_raw *= scale_penalty
    maturity_cap = _sample_maturity_cap(sample)
    confidence = round(min(epistemic_raw, maturity_cap), 2)

    thin_evidence = sufficiency in {DataSufficiency.COLD_START, DataSufficiency.PARTIAL} or sample < 7
    extreme_low_evidence = thin_evidence and (_is_extreme(happiness) or _is_extreme(stress))
    if extreme_low_evidence:
        confidence = round(min(confidence, maturity_cap) * 0.7, 2)
    if report.ambiguous_count > 0:
        confidence = round(min(confidence, 40.0), 2)

    warning = EarlyWarning.NONE
    if sufficiency == DataSufficiency.COLD_START:
        warning = EarlyWarning.INSUFFICIENT_DATA
    else:
        flags: list[EarlyWarning] = []
        if stress is not None and stress >= 70:
            flags.append(EarlyWarning.ELEVATED_STRESS)
        if happiness is not None and happiness <= 35:
            flags.append(EarlyWarning.LOW_HAPPINESS)
        if confidence is not None and confidence <= 35:
            flags.append(EarlyWarning.LOW_CONFIDENCE)
        if extreme_low_evidence:
            flags.append(EarlyWarning.EXTREME_SCORE_LOW_EVIDENCE)
        if len(flags) >= 2:
            # Prefer compound only when classic risk flags collide; keep extreme visible.
            classic = [f for f in flags if f != EarlyWarning.EXTREME_SCORE_LOW_EVIDENCE]
            if len(classic) >= 2:
                warning = EarlyWarning.COMPOUND_RISK
            elif EarlyWarning.EXTREME_SCORE_LOW_EVIDENCE in flags and classic:
                warning = classic[0]
            else:
                warning = flags[0]
        elif flags:
            warning = flags[0]

    contributors: list[dict[str, Any]] = []
    if avg_happ is not None:
        contributors.append(
            {"factor": "reported_happiness", "direction": "supports_happiness", "weight": 0.75, "value": avg_happ}
        )
    if avg_energy is not None:
        contributors.append(
            {"factor": "energy", "direction": "supports_happiness_and_confidence", "weight": 0.15, "value": avg_energy}
        )
    if avg_stress is not None:
        contributors.append(
            {"factor": "reported_stress", "direction": "supports_stress", "weight": 0.80, "value": avg_stress}
        )
    if alcohol_rate > 0:
        contributors.append(
            {"factor": "alcohol_frequency", "direction": "amplifies_stress", "weight": 0.08, "value": alcohol_rate}
        )
    if avg_prod is not None:
        contributors.append(
            {"factor": "productivity", "direction": "supports_confidence", "weight": 0.45, "value": avg_prod}
        )
    if gym_rate is not None:
        contributors.append(
            {"factor": "gym_adherence", "direction": "supports_confidence", "weight": 0.15, "value": gym_rate}
        )

    suggested: list[dict[str, Any]] = []
    if warning in {EarlyWarning.ELEVATED_STRESS, EarlyWarning.COMPOUND_RISK}:
        suggested.append(
            {
                "id": "review_stress_drivers",
                "capability_class": "EXPLAIN",
                "title": "Review recent stress drivers",
                "rationale": "Stress score elevated relative to the formula window; examine sleep and alcohol signals.",
            }
        )
    if warning in {EarlyWarning.LOW_HAPPINESS, EarlyWarning.COMPOUND_RISK}:
        suggested.append(
            {
                "id": "inspect_happiness_contributors",
                "capability_class": "EXPLAIN",
                "title": "Inspect happiness contributors",
                "rationale": "Happiness is independently low; energy/sleep may be undercutting reported mood.",
            }
        )
    if warning == EarlyWarning.LOW_CONFIDENCE:
        suggested.append(
            {
                "id": "stabilize_productivity_routine",
                "capability_class": "ANALYZE",
                "title": "Analyze productivity and gym consistency",
                "rationale": "Confidence uses productivity/energy/gym — not inverted stress.",
            }
        )
    if sufficiency in {DataSufficiency.COLD_START, DataSufficiency.PARTIAL}:
        suggested.append(
            {
                "id": "increase_checkin_coverage",
                "capability_class": "ANALYZE",
                "title": "Increase check-in coverage",
                "rationale": f"Window has {missing} missing days; denser observations improve baseline stability.",
            }
        )
    if not suggested:
        suggested.append(
            {
                "id": "maintain_observation_cadence",
                "capability_class": "ANALYZE",
                "title": "Maintain observation cadence",
                "rationale": "Current window supports stable ANALYZE/EXPLAIN without early-warning flags.",
            }
        )

    features = {
        "window_days": window_days,
        "avg_happiness_raw": avg_happ,
        "avg_stress_raw": avg_stress,
        "avg_energy_raw": avg_energy,
        "avg_productivity_raw": avg_prod,
        "avg_sleep_hours": avg_sleep,
        "gym_rate": gym_rate,
        "alcohol_rate": alcohol_rate,
        "happiness_neq_100_minus_stress": True,
        "avg_happiness_normalized": happ_n,
        "avg_stress_normalized": stress_n,
        "happiness_pre_clamp": happ_pre_clamp,
        "stress_pre_clamp": stress_pre_clamp,
        "agency_score": agency_score,
        "epistemic_raw": round(epistemic_raw, 2),
        "sample_maturity_cap": maturity_cap,
        "domain_coverage": round(domain_coverage, 4),
        "day_coverage": round(day_coverage, 4),
        "calibration_status": calibration_status,
        "extreme_score_low_evidence": extreme_low_evidence,
        "scale_penalty": round(scale_penalty, 4),
        "missing_domains": [
            name
            for name, present in (
                ("happiness", avg_happ is not None),
                ("stress", avg_stress is not None),
                ("energy", avg_energy is not None),
                ("productivity", avg_prod is not None),
                ("sleep", avg_sleep is not None),
                ("gym", gym_rate is not None),
                ("schedule", False),  # V1 has no schedule domain
            )
            if not present
        ],
        **report.as_features(),
    }

    baselines = {
        str(w): _baseline_features(days, w, as_of) for w in BASELINE_WINDOWS
    }

    return WellbeingResult(
        formula_id=FORMULA_ID,
        formula_version=FORMULA_VERSION,
        happiness=happiness,
        stress=stress,
        confidence=confidence,
        early_warning=warning,
        data_sufficiency=sufficiency,
        sample_size=sample,
        missing_days=missing,
        period_start=start.isoformat(),
        period_end=as_of.isoformat(),
        features=features,
        contributors=contributors,
        suggested_actions=suggested,
        explanation={
            "summary": (
                f"Wellbeing v1 over {sample} check-in days "
                f"({start.isoformat()} → {as_of.isoformat()})."
            ),
            "happiness_definition": (
                "Composite of reported happiness (primary), energy, and sleep proximity to 7.5h. "
                "Not equal to 100 minus stress."
            ),
            "stress_definition": "Reported stress scaled to 0–100, amplified by alcohol rate and short sleep.",
            "confidence_definition": (
                "Epistemic estimation confidence from day coverage, domain coverage, "
                "data sufficiency, calibration status, and sample-maturity caps. "
                "Agency (productivity/energy/gym) is stored separately as features.agency_score."
            ),
            "input_scale_policy": (
                "Explicit per-field scale or known legacy adapter only. "
                f"Normalized once to 0–100 ({NORMALIZATION_VERSION}); "
                "no magnitude inference; clamp only after composition."
            ),
            "measurement_contract_version": MEASUREMENT_CONTRACT_VERSION,
            "input_normalization_version": NORMALIZATION_VERSION,
            "autonomy": "ANALYZE/EXPLAIN only; suggested_actions are not RECOMMEND capability.",
            "cold_start_policy": f"Scores marked COLD_START below {COLD_START_MIN_DAYS} days.",
            "calibration_status": calibration_status,
        },
        as_of_global_position=max_pos,
        baselines=baselines,
    )
