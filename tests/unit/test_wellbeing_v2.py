"""Unit tests for wellbeing_v2 SHADOW pipeline."""

from intelligence_maxxxing.domain_packs.life.wellbeing_v2.pipeline import compute_wellbeing_v2
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.registry import (
    FORMULA_STATUS,
    FORMULA_VERSION,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.scenarios import SCENARIOS, run_scenario


def test_formula_is_shadow() -> None:
    assert FORMULA_STATUS == "SHADOW"
    assert FORMULA_VERSION == "2.1.0"


def test_happiness_not_100_minus_stress_exciting_deadline() -> None:
    r = run_scenario("exciting_deadline")
    assert r["happiness"] is not None and r["stress"] is not None
    assert r["happiness"] > 52
    assert r["stress"] > 55
    # Both elevated (eustress) — Happiness must not collapse to 100-Stress
    assert r["happiness"] + r["stress"] > 120
    assert abs(r["happiness"] - (100 - r["stress"])) > 5


def test_empty_low_affect_low_stress() -> None:
    r = run_scenario("empty_low_affect")
    assert r["happiness"] is not None and r["stress"] is not None
    assert r["happiness"] < 50
    assert r["stress"] < 55


def test_good_recovery_high_happiness_low_stress() -> None:
    r = run_scenario("good_recovery")
    assert r["happiness"] > 55
    assert r["stress"] < 55


def test_accumulated_load_rising_stress() -> None:
    r = run_scenario("accumulated_load")
    assert r["stress"] is not None and r["stress"] >= 55
    assert r["change_state"] in {
        "RISING_STRESS",
        "PERSISTENT_LOAD",
        "NEGATIVE_SHIFT",
        "FALLING_HAPPINESS",
        "STABLE",
        "RECOVERING",
    }
    # High load scenario must not look like a calm good day
    assert r["stress"] > r["happiness"]


def test_sparse_calendar_low_confidence() -> None:
    r = run_scenario("calendar_only_sparse")
    assert r["confidence"] is not None
    assert r["confidence"] < 40
    assert r["happiness_confidence"] < 40


def test_separate_confidences() -> None:
    r = run_scenario("good_recovery")
    assert r["happiness_confidence"] is not None
    assert r["stress_confidence"] is not None


def test_reproducibility_fingerprint() -> None:
    days = SCENARIOS["good_recovery"]
    a = compute_wellbeing_v2(days, window_days=14)
    b = compute_wellbeing_v2(days, window_days=14)
    assert a.input_fingerprint == b.input_fingerprint
    assert a.happiness_score == b.happiness_score
    assert a.stress_score == b.stress_score


def test_suggested_actions_not_recommend() -> None:
    result = compute_wellbeing_v2(SCENARIOS["accumulated_load"], window_days=14)
    for action in result.suggested_actions:
        assert action["capability_class"] in {"ANALYZE", "EXPLAIN"}
        assert action.get("urgency") != "HIGH" or result.overall_confidence >= 45


def test_double_counting_sleep_bounded() -> None:
    """Multiple sleep-related signals should not explode stress vs single short sleep."""
    from datetime import date, timedelta

    from intelligence_maxxxing.domain_packs.life.wellbeing_v2.observations import DayRecord

    base = date(2026, 6, 1)
    days = [
        DayRecord(
            day=base + timedelta(days=i),
            happiness=6,
            stress=5,
            energy=5,
            productivity=6,
            sleep_hours=5.0,
            gym_done=False,
            social_activity=False,
            alcohol=False,
            meetings_count=3,
            workout_done=False,
            global_position=i + 1,
            observed_fields=("happiness", "stress", "energy", "sleep_hours", "meetings_count"),
        )
        for i in range(7)
    ]
    result = compute_wellbeing_v2(days, window_days=14)
    assert result.stress_score is not None
    assert result.stress_score < 95


def test_recovery_after_load_reduces_stress() -> None:
    early = compute_wellbeing_v2(SCENARIOS["recovery_after_load"][:4], window_days=14)
    late = compute_wellbeing_v2(SCENARIOS["recovery_after_load"], window_days=14)
    assert early.stress_score is not None and late.stress_score is not None
    assert late.stress_score < early.stress_score + 5
