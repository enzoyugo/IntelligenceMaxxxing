"""Stage 3.1 terminal vs interim classification."""

from intelligence_maxxxing.domain_packs.life.methods.bayesian_bootstrap import classify_belief_state


def test_target_must_be_reached_for_supported() -> None:
    state = classify_belief_state(
        phase="PROSPECTIVE_VALIDATION",
        n_sufficient=21,
        n_below=21,
        p_delta_gt_0=0.99,
        p_delta_ge_mmd=0.99,
        ci90_low=0.5,
        prospective_target=42,
        expired=False,
    )
    assert state == "PROSPECTIVE_SUPPORTED"


def test_group_minimums_must_be_reached_for_supported() -> None:
    state = classify_belief_state(
        phase="PROSPECTIVE_VALIDATION",
        n_sufficient=40,
        n_below=2,
        p_delta_gt_0=0.99,
        p_delta_ge_mmd=0.99,
        ci90_low=0.5,
        prospective_target=42,
        expired=False,
    )
    assert state == "PROSPECTIVE_COLLECTING"


def test_no_outcome_based_early_stopping() -> None:
    state = classify_belief_state(
        phase="PROSPECTIVE_VALIDATION",
        n_sufficient=7,
        n_below=7,
        p_delta_gt_0=0.999,
        p_delta_ge_mmd=0.999,
        ci90_low=3.0,
        prospective_target=42,
        expired=False,
    )
    assert state == "PROSPECTIVE_COLLECTING"


def test_controlled_test_clock_blocked_outside_test_env(monkeypatch) -> None:
    monkeypatch.setenv("ENGINE_ENV", "production")
    import pytest

    from intelligence_maxxxing.infrastructure.clock.controlled_test_clock import ControlledTestClock

    with pytest.raises(RuntimeError, match="ENGINE_ENV=test"):
        ControlledTestClock()
