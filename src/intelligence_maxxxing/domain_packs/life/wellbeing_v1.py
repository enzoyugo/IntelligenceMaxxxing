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

FORMULA_ID = "wellbeing_v1"
FORMULA_VERSION = "1.0"
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


def _scale_1_10_to_100(value: float) -> float:
    return _clamp((value - 1.0) / 9.0 * 100.0)


def extract_checkin_days(rows: list[Any]) -> list[CheckInDay]:
    """Extract daily check-in features from projected observation rows."""
    by_day: dict[date, CheckInDay] = {}
    ordered = sorted(
        rows,
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
        by_day[day] = CheckInDay(
            day=day,
            happiness=_f("happiness"),
            stress=_f("stress"),
            energy=_f("energy"),
            productivity=_f("productivity"),
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
) -> WellbeingResult:
    """Compute Happiness / Stress / Confidence for a trailing window.

    Happiness uses reported happiness + energy + sleep quality signals.
    Stress uses reported stress + alcohol + meeting load proxies (meetings not
    always present; alcohol and low sleep amplify).
    Confidence is separate: productivity consistency + gym adherence + energy
    stability — not a transform of stress.
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
            features={"window_days": window_days},
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

    # Happiness (0-100): independent composite — NOT (100 - stress).
    happiness: float | None = None
    if avg_happ is not None:
        base = _scale_1_10_to_100(avg_happ)
        energy_boost = ((_scale_1_10_to_100(avg_energy) - 50.0) * 0.15) if avg_energy else 0.0
        sleep_boost = 0.0
        if avg_sleep is not None:
            # Peak around 7.5h; mild penalty outside 6–9.
            sleep_boost = _clamp(100.0 - abs(avg_sleep - 7.5) * 12.0, 0.0, 100.0) * 0.10 - 5.0
        happiness = round(_clamp(base + energy_boost + sleep_boost), 2)

    # Stress (0-100): higher is worse; alcohol/low sleep amplify.
    stress: float | None = None
    if avg_stress is not None:
        base_s = _scale_1_10_to_100(avg_stress)
        amp = alcohol_rate * 8.0
        if avg_sleep is not None and avg_sleep < 6.0:
            amp += (6.0 - avg_sleep) * 4.0
        stress = round(_clamp(base_s + amp), 2)

    # Confidence (0-100): separate — productivity + energy stability + gym.
    confidence: float | None = None
    if avg_prod is not None or avg_energy is not None:
        prod_c = _scale_1_10_to_100(avg_prod) if avg_prod is not None else 50.0
        energy_c = _scale_1_10_to_100(avg_energy) if avg_energy is not None else 50.0
        gym_c = (gym_rate * 100.0) if gym_rate is not None else 40.0
        # Energy variance penalty (stability).
        stability = 100.0
        if len(energy_raw) >= 2:
            e_mean = mean(energy_raw)
            variance = mean([(e - e_mean) ** 2 for e in energy_raw])
            stability = _clamp(100.0 - variance * 8.0)
        confidence = round(_clamp(0.45 * prod_c + 0.30 * energy_c + 0.15 * gym_c + 0.10 * stability), 2)

    if sample < COLD_START_MIN_DAYS:
        sufficiency = DataSufficiency.COLD_START
    elif missing > window_days // 2:
        sufficiency = DataSufficiency.PARTIAL
    elif sample >= 10 and missing <= 2:
        sufficiency = DataSufficiency.RICH
    else:
        sufficiency = DataSufficiency.ADEQUATE

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
        if len(flags) >= 2:
            warning = EarlyWarning.COMPOUND_RISK
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
                "Separate score from productivity, energy level/stability, and gym adherence."
            ),
            "autonomy": "ANALYZE/EXPLAIN only; suggested_actions are not RECOMMEND capability.",
            "cold_start_policy": f"Scores marked COLD_START below {COLD_START_MIN_DAYS} days.",
        },
        as_of_global_position=max_pos,
        baselines=baselines,
    )
