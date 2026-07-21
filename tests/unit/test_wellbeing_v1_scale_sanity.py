"""V1 scale contract: CheckInDay holds canonical 0–100; no magnitude heuristic."""

from datetime import date, timedelta

from intelligence_maxxxing.domain_packs.life.measurement_scale import (
    MEASUREMENT_CONTRACT_VERSION,
    NORMALIZATION_VERSION,
    MeasurementScale,
    to_canonical_0_100,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v1 import (
    CheckInDay,
    DataSufficiency,
    FORMULA_VERSION,
    compute_wellbeing_v1,
)


def _day100(offset: int, *, happiness: float, stress: float) -> CheckInDay:
    base = date(2026, 7, 10)
    return CheckInDay(
        day=base + timedelta(days=offset),
        happiness=happiness,
        stress=stress,
        energy=55.0,
        productivity=50.0,
        sleep_hours=7.0,
        gym_done=True,
        social_activity=False,
        alcohol=False,
        global_position=offset + 1,
    )


def test_formula_version_is_1_2() -> None:
    assert FORMULA_VERSION == "1.2"


def test_no_magnitude_helper_on_wellbeing_v1() -> None:
    import intelligence_maxxxing.domain_packs.life.wellbeing_v1 as mod

    assert not hasattr(mod, "_to_score_100")


def test_no_double_scaling_saturation_on_percent_inputs() -> None:
    days = [_day100(i, happiness=66.0, stress=37.0) for i in range(5)]
    result = compute_wellbeing_v1(days, window_days=14, as_of=date(2026, 7, 14))
    assert result.formula_version == "1.2"
    assert result.happiness is not None and result.happiness < 90
    assert result.stress is not None and result.stress < 90
    assert result.happiness != 100.0
    assert result.stress != 100.0
    assert result.features["input_normalization_version"] == NORMALIZATION_VERSION
    assert result.features["measurement_contract_version"] == MEASUREMENT_CONTRACT_VERSION


def test_five_day_partial_confidence_capped() -> None:
    days = [_day100(i, happiness=66.0, stress=37.0) for i in range(5)]
    result = compute_wellbeing_v1(days, window_days=14, as_of=date(2026, 7, 14))
    assert result.sample_size == 5
    assert result.data_sufficiency == DataSufficiency.PARTIAL
    assert result.confidence is not None
    assert result.confidence <= 45.0
    assert result.features["calibration_status"] == "uncalibrated"
    assert result.features["sample_maturity_cap"] == 45.0


def test_likert_authored_canonical_inputs() -> None:
    base = date(2026, 7, 10)
    days = [
        CheckInDay(
            day=base + timedelta(days=i),
            happiness=to_canonical_0_100(7.0, MeasurementScale.LIKERT_1_10),
            stress=to_canonical_0_100(4.0, MeasurementScale.LIKERT_1_10),
            energy=to_canonical_0_100(7.0, MeasurementScale.LIKERT_1_10),
            productivity=to_canonical_0_100(7.0, MeasurementScale.LIKERT_1_10),
            sleep_hours=7.5,
            gym_done=True,
            social_activity=False,
            alcohol=False,
            global_position=i + 1,
        )
        for i in range(7)
    ]
    result = compute_wellbeing_v1(days, window_days=7, as_of=date(2026, 7, 16))
    assert result.happiness is not None and 50 <= result.happiness <= 90
    assert result.stress is not None and 20 <= result.stress <= 55


def test_low_percent_values_not_reinterpreted_as_likert() -> None:
    """5/100 and 10/100 must stay near those levels — not Likert→~44 / 100."""
    days = [_day100(i, happiness=5.0, stress=10.0) for i in range(5)]
    result = compute_wellbeing_v1(days, window_days=14, as_of=date(2026, 7, 14))
    assert result.happiness is not None
    assert result.stress is not None
    assert result.happiness < 25.0
    assert result.stress < 30.0
    assert abs(result.features["avg_happiness_normalized"] - 5.0) < 0.01
    assert abs(result.features["avg_stress_normalized"] - 10.0) < 0.01


def test_missing_values_do_not_become_max() -> None:
    base = date(2026, 7, 10)
    days = [
        CheckInDay(
            day=base + timedelta(days=i),
            happiness=60.0,
            stress=40.0,
            energy=None,
            productivity=None,
            sleep_hours=None,
            gym_done=None,
            social_activity=None,
            alcohol=None,
            global_position=i + 1,
        )
        for i in range(5)
    ]
    result = compute_wellbeing_v1(days, window_days=14, as_of=date(2026, 7, 14))
    assert result.happiness is not None and result.happiness < 100
    assert "energy" in result.features["missing_domains"]
    assert "schedule" in result.features["missing_domains"]
