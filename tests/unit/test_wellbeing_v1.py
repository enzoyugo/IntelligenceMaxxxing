"""Unit tests for wellbeing_v1 formulas."""

from datetime import date, timedelta

from intelligence_maxxxing.domain_packs.life.wellbeing_v1 import (
    CheckInDay,
    DataSufficiency,
    EarlyWarning,
    compute_wellbeing_v1,
)


def _day(
    offset: int,
    *,
    happiness: float = 7.0,
    stress: float = 4.0,
    energy: float = 7.0,
    productivity: float = 7.0,
    sleep: float = 7.5,
    gym: bool = True,
    alcohol: bool = False,
) -> CheckInDay:
    base = date(2026, 7, 10)
    return CheckInDay(
        day=base + timedelta(days=offset),
        happiness=happiness,
        stress=stress,
        energy=energy,
        productivity=productivity,
        sleep_hours=sleep,
        gym_done=gym,
        social_activity=False,
        alcohol=alcohol,
        global_position=offset + 1,
    )


def test_cold_start_insufficient_data() -> None:
    result = compute_wellbeing_v1([], window_days=14, as_of=date(2026, 7, 20))
    assert result.happiness is None
    assert result.early_warning == EarlyWarning.INSUFFICIENT_DATA
    assert result.data_sufficiency == DataSufficiency.COLD_START
    assert result.sample_size == 0


def test_happiness_not_100_minus_stress() -> None:
    days = [_day(i, happiness=8.0, stress=3.0) for i in range(7)]
    result = compute_wellbeing_v1(days, window_days=7, as_of=date(2026, 7, 16))
    assert result.happiness is not None
    assert result.stress is not None
    assert abs(result.happiness - (100.0 - result.stress)) > 0.5
    assert result.features["happiness_neq_100_minus_stress"] is True


def test_agency_independent_of_stress() -> None:
    """Agency (features) tracks productivity/energy/gym; epistemic confidence is separate."""
    high_stress = [_day(i, stress=9.0, productivity=9.0, energy=8.0, gym=True) for i in range(10)]
    low_stress = [_day(i, stress=2.0, productivity=3.0, energy=3.0, gym=False) for i in range(10)]
    high = compute_wellbeing_v1(high_stress, window_days=10, as_of=date(2026, 7, 19))
    low = compute_wellbeing_v1(low_stress, window_days=10, as_of=date(2026, 7, 19))
    assert high.features["agency_score"] is not None and low.features["agency_score"] is not None
    assert high.features["agency_score"] > low.features["agency_score"]
    assert high.stress is not None and low.stress is not None
    assert high.stress > low.stress
    # Same sample size → epistemic confidence in the same maturity band.
    assert high.confidence is not None and low.confidence is not None
    assert high.confidence <= 60.0  # 7–13 day cap


def test_suggested_actions_are_analyze_explain_not_recommend() -> None:
    days = [_day(i, stress=9.0, happiness=2.0) for i in range(10)]
    result = compute_wellbeing_v1(days, window_days=10, as_of=date(2026, 7, 19))
    assert result.suggested_actions
    for action in result.suggested_actions:
        assert action["capability_class"] in {"ANALYZE", "EXPLAIN"}
        assert action["capability_class"] != "RECOMMEND"


def test_baselines_7_30_90_present() -> None:
    days = [_day(i) for i in range(14)]
    result = compute_wellbeing_v1(days, window_days=14, as_of=date(2026, 7, 23))
    assert set(result.baselines.keys()) == {"7", "30", "90"}


def test_elevated_stress_early_warning() -> None:
    days = [_day(i, stress=9.0, happiness=7.0) for i in range(10)]
    result = compute_wellbeing_v1(days, window_days=10, as_of=date(2026, 7, 19))
    assert result.early_warning in {EarlyWarning.ELEVATED_STRESS, EarlyWarning.COMPOUND_RISK}
