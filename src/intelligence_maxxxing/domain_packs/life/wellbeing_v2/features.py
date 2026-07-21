"""Feature engineering with personal baselines and domain caps inputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from intelligence_maxxxing.domain_packs.life.wellbeing_v2.math_utils import (
    baseline_maturity,
    clamp,
    mad,
    mean_or_none,
    robust_z,
    scale_0_100,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.observations import DayRecord


@dataclass(frozen=True)
class FeatureBundle:
    as_of: date
    sample_size: int
    missing_days: int
    window_days: int
    # normalized [-1,1] domain signals for composition
    signals: dict[str, float | None]
    baselines: dict[str, Any]
    maturity: dict[str, str]
    observed_domains: frozenset[str]
    sleep_debt_3d: float | None
    consecutive_short_sleep: int
    load_state: float  # accumulated load after EWMA walk
    meeting_pressure: float | None
    overdue_proxy: float | None  # from meetings as weak proxy when tasks absent


def _history(days: list[DayRecord], attr: str) -> list[float]:
    out: list[float] = []
    for d in days:
        v = getattr(d, attr)
        if v is None:
            continue
        if isinstance(v, bool):
            out.append(1.0 if v else 0.0)
        else:
            out.append(float(v))
    return out


def build_features(
    days: list[DayRecord],
    *,
    as_of: date | None = None,
    window_days: int = 14,
    retention: float = 0.72,
) -> FeatureBundle:
    if as_of is None:
        as_of = max((d.day for d in days), default=date.today())
    start = as_of - timedelta(days=window_days - 1)
    window = [d for d in days if start <= d.day <= as_of]
    present = {d.day for d in window}
    expected = {start + timedelta(days=i) for i in range(window_days)}
    missing = len(expected - present)

    # Walk accumulation chronologically over all history up to as_of
    hist = [d for d in days if d.day <= as_of]
    load = 0.0
    for d in hist:
        new_load = 0.0
        recovery = 0.0
        if d.stress is not None:
            # Canonical 0–100: stress above midpoint contributes load.
            new_load += max(0.0, (d.stress - 50.0) / 50.0)
        if d.meetings_count is not None:
            new_load += min(1.0, d.meetings_count / 8.0) * 0.4
        if d.alcohol:
            new_load += 0.25
        if d.sleep_hours is not None and d.sleep_hours < 6.0:
            new_load += (6.0 - d.sleep_hours) * 0.2
        if d.sleep_hours is not None and d.sleep_hours >= 7.0:
            recovery += 0.15
        if d.social_activity:
            recovery += 0.1
        if d.workout_done or d.gym_done:
            recovery += 0.08
        if d.energy is not None and d.energy >= 70.0:
            recovery += 0.05
        load = retention * load + new_load - recovery
        load = clamp(load, 0.0, 3.5)

    # Sleep debt 3d
    last3 = [d for d in hist if as_of - timedelta(days=2) <= d.day <= as_of]
    sleeps = [d.sleep_hours for d in last3 if d.sleep_hours is not None]
    sleep_debt = None
    if sleeps:
        sleep_debt = max(0.0, 7.5 - (sum(sleeps) / len(sleeps)))

    consec = 0
    for d in reversed(hist):
        if d.sleep_hours is not None and d.sleep_hours < 6.5:
            consec += 1
        elif d.sleep_hours is not None:
            break

    sleep_hist = _history(hist, "sleep_hours")
    energy_hist = _history(hist, "energy")
    happ_hist = _history(hist, "happiness")
    stress_hist = _history(hist, "stress")
    prod_hist = _history(hist, "productivity")
    meet_hist = _history(hist, "meetings_count")

    latest = next((d for d in reversed(hist) if d.day <= as_of), None)

    def rz(attr: str, hist_vals: list[float]) -> float | None:
        if latest is None:
            return None
        cur = getattr(latest, attr)
        if cur is None:
            return None
        if isinstance(cur, bool):
            cur_f = 1.0 if cur else 0.0
        else:
            cur_f = float(cur)
        if attr in {"happiness", "stress", "energy", "productivity"}:
            absolute = scale_0_100(cur_f)
        elif attr == "sleep_hours":
            absolute = clamp((cur_f - 7.5) / 2.0, -1.0, 1.0)
        else:
            absolute = clamp(cur_f, -1.0, 1.0)
        # MAD threshold scaled for canonical 0–100 (was 0.2 on Likert 1–10).
        mad_floor = 2.0 if attr in {"happiness", "stress", "energy", "productivity"} else 0.2
        if len(hist_vals) < 3 or mad(hist_vals) < mad_floor:
            # Low variance / cold start: absolute scale carries the signal
            return absolute
        rz_eps = 2.5 if attr in {"happiness", "stress", "energy", "productivity"} else 0.25
        relative = clamp(robust_z(cur_f, hist_vals, epsilon=rz_eps) / 3.5, -1.0, 1.0)
        # Blend so personal deviations matter without zeroing stable good/bad days
        return clamp(0.55 * relative + 0.45 * (absolute or 0.0))

    signals: dict[str, float | None] = {
        "happiness_raw": scale_0_100(latest.happiness) if latest else None,
        "stress_raw": scale_0_100(latest.stress) if latest else None,
        "energy_rz": rz("energy", energy_hist),
        "happiness_rz": rz("happiness", happ_hist),
        "stress_rz": rz("stress", stress_hist),
        "productivity_rz": rz("productivity", prod_hist),
        "sleep_rz": rz("sleep_hours", sleep_hist),
        "sleep_debt_n": clamp((sleep_debt or 0.0) / 2.5, 0.0, 1.0) if sleep_debt is not None else None,
        "gym": (1.0 if latest and (latest.gym_done or latest.workout_done) else 0.0)
        if latest and (latest.gym_done is not None or latest.workout_done is not None)
        else None,
        "social": (1.0 if latest and latest.social_activity else 0.0)
        if latest and latest.social_activity is not None
        else None,
        "alcohol": (1.0 if latest and latest.alcohol else 0.0)
        if latest and latest.alcohol is not None
        else None,
        "meetings_n": (
            clamp((latest.meetings_count or 0.0) / 8.0, 0.0, 1.0)
            if latest and latest.meetings_count is not None
            else None
        ),
        "load_n": clamp(load / 2.5, 0.0, 1.0),
        "consec_short_sleep_n": clamp(consec / 3.0, 0.0, 1.0),
    }

    domains = set()
    if latest:
        for f in latest.observed_fields:
            if f in {"happiness", "stress", "energy"}:
                domains.add("subjective")
            if f == "sleep_hours":
                domains.add("sleep")
            if f in {"gym_done", "social_activity"}:
                domains.add("activity")
            if f == "meetings_count":
                domains.add("schedule")
            if f == "productivity":
                domains.add("tasks")

    baselines = {
        "sleep_median": mean_or_none(sleep_hist[-30:]) if sleep_hist else None,
        "energy_median": mean_or_none(energy_hist[-30:]) if energy_hist else None,
        "happiness_median": mean_or_none(happ_hist[-30:]) if happ_hist else None,
        "stress_median": mean_or_none(stress_hist[-30:]) if stress_hist else None,
        "n_sleep": len(sleep_hist),
        "n_energy": len(energy_hist),
        "n_happiness": len(happ_hist),
        "n_stress": len(stress_hist),
    }
    maturity = {
        "sleep": baseline_maturity(len(sleep_hist)),
        "energy": baseline_maturity(len(energy_hist)),
        "happiness": baseline_maturity(len(happ_hist)),
        "stress": baseline_maturity(len(stress_hist)),
        "meetings": baseline_maturity(len(meet_hist)),
    }

    return FeatureBundle(
        as_of=as_of,
        sample_size=len(window),
        missing_days=missing,
        window_days=window_days,
        signals=signals,
        baselines=baselines,
        maturity=maturity,
        observed_domains=frozenset(domains),
        sleep_debt_3d=sleep_debt,
        consecutive_short_sleep=consec,
        load_state=load,
        meeting_pressure=signals["meetings_n"],
        overdue_proxy=signals["meetings_n"],  # tasks not always in Engine observations
    )
