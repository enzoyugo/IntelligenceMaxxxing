"""Deterministic synthetic scenarios for wellbeing_v2 simulation harness."""

from __future__ import annotations

from datetime import date, timedelta

from intelligence_maxxxing.domain_packs.life.wellbeing_v2.observations import DayRecord
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.pipeline import compute_wellbeing_v2


def _day(
    base: date,
    offset: int,
    *,
    happiness: float | None = 7.0,
    stress: float | None = 4.0,
    energy: float | None = 7.0,
    productivity: float | None = 7.0,
    sleep: float | None = 7.5,
    gym: bool | None = False,
    social: bool | None = False,
    alcohol: bool | None = False,
    meetings: float | None = 2.0,
) -> DayRecord:
    return DayRecord(
        day=base + timedelta(days=offset),
        happiness=happiness,
        stress=stress,
        energy=energy,
        productivity=productivity,
        sleep_hours=sleep,
        gym_done=gym,
        social_activity=social,
        alcohol=alcohol,
        meetings_count=meetings,
        workout_done=gym,
        global_position=offset + 1,
        observed_fields=("happiness", "stress", "energy", "productivity", "sleep_hours", "meetings_count"),
    )


BASE = date(2026, 7, 1)


SCENARIOS: dict[str, list[DayRecord]] = {
    "good_recovery": [
        _day(BASE, i, happiness=8, stress=2, energy=8, sleep=8.0, social=True, meetings=1, gym=True)
        for i in range(7)
    ],
    "exciting_deadline": [
        _day(BASE, i, happiness=8, stress=8, energy=8, productivity=9, sleep=7.0, meetings=6, gym=False)
        for i in range(7)
    ],
    "empty_low_affect": [
        _day(BASE, i, happiness=3, stress=2, energy=3, productivity=3, sleep=7.5, meetings=0, social=False)
        for i in range(7)
    ],
    "accumulated_load": [
        _day(BASE, i, happiness=4, stress=7 + min(i, 2), energy=3, sleep=5.5, meetings=7, alcohol=i % 2 == 0)
        for i in range(7)
    ],
    "calendar_only_sparse": [
        DayRecord(
            day=BASE + timedelta(days=i),
            happiness=None,
            stress=None,
            energy=None,
            productivity=None,
            sleep_hours=None,
            gym_done=None,
            social_activity=None,
            alcohol=None,
            meetings_count=4.0 if i % 2 == 0 else 2.0,
            workout_done=None,
            global_position=i + 1,
            observed_fields=("meetings_count",),
        )
        for i in range(3)
    ],
    "conflicting_signals": [
        _day(BASE, i, happiness=8, stress=9, energy=8, sleep=8.0, meetings=1) for i in range(5)
    ],
    "outlier_night": [
        *[_day(BASE, i, happiness=7, stress=4, energy=7, sleep=7.5) for i in range(5)],
        _day(BASE, 5, happiness=7, stress=4, energy=6, sleep=3.0),
    ],
    "recovery_after_load": [
        *[_day(BASE, i, happiness=4, stress=8, energy=3, sleep=5.5, meetings=7) for i in range(4)],
        *[_day(BASE, i, happiness=7, stress=3, energy=7, sleep=8.0, meetings=1, social=True) for i in range(4, 8)],
    ],
}


def run_scenario(name: str) -> dict:
    days = SCENARIOS[name]
    as_of = max(d.day for d in days)
    result = compute_wellbeing_v2(days, window_days=14, as_of=as_of)
    return {
        "name": name,
        "happiness": result.happiness_score,
        "stress": result.stress_score,
        "confidence": result.confidence_score,
        "change_state": result.change_state,
        "happiness_confidence": result.happiness["confidence"],
        "stress_confidence": result.stress["confidence"],
    }
