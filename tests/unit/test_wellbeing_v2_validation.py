"""Comparative baselines, leakage guard, and ablation smoke for V2."""

from datetime import date, timedelta

from intelligence_maxxxing.domain_packs.life.wellbeing_v1 import compute_wellbeing_v1
from intelligence_maxxxing.domain_packs.life.wellbeing_v1 import CheckInDay
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.observations import DayRecord
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.pipeline import compute_wellbeing_v2
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.scenarios import SCENARIOS


def _to_v1_days(days: list[DayRecord]) -> list[CheckInDay]:
    return [
        CheckInDay(
            day=d.day,
            happiness=d.happiness,
            stress=d.stress,
            energy=d.energy,
            productivity=d.productivity,
            sleep_hours=d.sleep_hours,
            gym_done=d.gym_done,
            social_activity=d.social_activity,
            alcohol=d.alcohol,
            global_position=d.global_position,
        )
        for d in days
    ]


def test_v2_differs_from_constant_50_on_recovery() -> None:
    days = SCENARIOS["good_recovery"]
    v2 = compute_wellbeing_v2(days, window_days=14)
    assert v2.happiness_score is not None
    assert abs(v2.happiness_score - 50.0) > 3


def test_v2_vs_v1_shadow_comparison_runs() -> None:
    days = SCENARIOS["exciting_deadline"]
    v1 = compute_wellbeing_v1(_to_v1_days(days), window_days=14, as_of=max(d.day for d in days))
    v2 = compute_wellbeing_v2(days, window_days=14)
    assert v1.happiness is not None and v2.happiness_score is not None
    # Both can be high; independence preserved in both
    assert abs(v2.happiness_score - (100 - (v2.stress_score or 0))) > 1


def test_no_future_leakage() -> None:
    """Observations after as_of must not affect scores."""
    base = date(2026, 5, 1)
    # Canonical 0–100 on DayRecord (Likert mid ≈ 44.44; high/low extremes).
    past = [
        DayRecord(
            day=base + timedelta(days=i),
            happiness=50.0,
            stress=50.0,
            energy=50.0,
            productivity=50.0,
            sleep_hours=7.0,
            gym_done=False,
            social_activity=False,
            alcohol=False,
            meetings_count=2,
            workout_done=False,
            global_position=i + 1,
            observed_fields=("happiness", "stress", "energy", "sleep_hours"),
        )
        for i in range(5)
    ]
    future = DayRecord(
        day=base + timedelta(days=10),
        happiness=100.0,
        stress=0.0,
        energy=100.0,
        productivity=100.0,
        sleep_hours=9.0,
        gym_done=True,
        social_activity=True,
        alcohol=False,
        meetings_count=0,
        workout_done=True,
        global_position=99,
        observed_fields=("happiness", "stress", "energy", "sleep_hours"),
    )
    as_of = base + timedelta(days=4)
    a = compute_wellbeing_v2(past, window_days=14, as_of=as_of)
    b = compute_wellbeing_v2([*past, future], window_days=14, as_of=as_of)
    assert a.happiness_score == b.happiness_score
    assert a.stress_score == b.stress_score
    assert a.input_fingerprint == b.input_fingerprint


def test_ablation_without_subjective_lowers_confidence() -> None:
    full = SCENARIOS["good_recovery"]
    sparse = [
        DayRecord(
            day=d.day,
            happiness=None,
            stress=None,
            energy=None,
            productivity=None,
            sleep_hours=d.sleep_hours,
            gym_done=d.gym_done,
            social_activity=d.social_activity,
            alcohol=d.alcohol,
            meetings_count=d.meetings_count,
            workout_done=d.workout_done,
            global_position=d.global_position,
            observed_fields=("sleep_hours", "meetings_count"),
        )
        for d in full
    ]
    full_r = compute_wellbeing_v2(full, window_days=14)
    sparse_r = compute_wellbeing_v2(sparse, window_days=14)
    assert sparse_r.overall_confidence < full_r.overall_confidence


def test_sleep_only_baseline_weaker_than_full_model_signal() -> None:
    days = SCENARIOS["accumulated_load"]
    v2 = compute_wellbeing_v2(days, window_days=14)
    # Sleep-only heuristic: mean short sleep → high stress proxy
    sleeps = [d.sleep_hours for d in days if d.sleep_hours is not None]
    sleep_only_stress = max(0.0, min(100.0, (7.5 - sum(sleeps) / len(sleeps)) * 25 + 40))
    assert v2.stress_score is not None
    # Full model should not collapse to sleep-only (meetings/accumulation matter)
    assert abs(v2.stress_score - sleep_only_stress) > 0.5 or v2.stress_score > 50
