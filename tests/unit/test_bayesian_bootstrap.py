"""Unit tests for Bayesian Bootstrap Difference in Means v1."""

from intelligence_maxxxing.domain.common.epistemic import BeliefState, EvidencePhase
from intelligence_maxxxing.domain_packs.life.methods.bayesian_bootstrap import (
    bayesian_bootstrap_difference_in_means,
    classify_belief_state,
    derive_seed,
)


def test_bootstrap_reproducible() -> None:
    seed = derive_seed("exp_1", "1.0", "BASELINE_EXPLORATORY")
    a = bayesian_bootstrap_difference_in_means(
        sufficient=[8.0, 8.5, 9.0, 8.2, 8.8],
        below=[5.0, 5.5, 4.8, 5.2, 5.1],
        minimum_meaningful_difference=0.5,
        seed=seed,
        draws=2000,
    )
    b = bayesian_bootstrap_difference_in_means(
        sufficient=[8.0, 8.5, 9.0, 8.2, 8.8],
        below=[5.0, 5.5, 4.8, 5.2, 5.1],
        minimum_meaningful_difference=0.5,
        seed=seed,
        draws=2000,
    )
    assert a.posterior_median_delta == b.posterior_median_delta
    assert a.p_delta_gt_0 == b.p_delta_gt_0
    assert a.seed == seed


def test_positive_fixture_classifies_exploratory_positive() -> None:
    seed = derive_seed("exp_pos", "1.0", EvidencePhase.BASELINE_EXPLORATORY.value)
    result = bayesian_bootstrap_difference_in_means(
        sufficient=[8.0] * 10,
        below=[4.0] * 10,
        minimum_meaningful_difference=0.5,
        seed=seed,
        draws=5000,
    )
    assert result.p_delta_gt_0 >= 0.80
    state = classify_belief_state(
        phase=EvidencePhase.BASELINE_EXPLORATORY.value,
        n_sufficient=10,
        n_below=10,
        p_delta_gt_0=result.p_delta_gt_0,
        p_delta_ge_mmd=result.p_delta_ge_mmd,
        ci90_low=result.credible_interval_90_low,
    )
    assert state == BeliefState.EXPLORATORY_POSITIVE.value


def test_baseline_never_supported() -> None:
    seed = derive_seed("exp_strong", "1.0", EvidencePhase.BASELINE_EXPLORATORY.value)
    result = bayesian_bootstrap_difference_in_means(
        sufficient=[9.0] * 20,
        below=[3.0] * 20,
        minimum_meaningful_difference=0.5,
        seed=seed,
        draws=5000,
    )
    state = classify_belief_state(
        phase=EvidencePhase.BASELINE_EXPLORATORY.value,
        n_sufficient=20,
        n_below=20,
        p_delta_gt_0=result.p_delta_gt_0,
        p_delta_ge_mmd=result.p_delta_ge_mmd,
        ci90_low=result.credible_interval_90_low,
    )
    assert state != BeliefState.PROSPECTIVE_SUPPORTED.value
    assert state == BeliefState.EXPLORATORY_POSITIVE.value


def test_insufficient_never_supported() -> None:
    state = classify_belief_state(
        phase=EvidencePhase.BASELINE_EXPLORATORY.value,
        n_sufficient=2,
        n_below=2,
        p_delta_gt_0=0.99,
        p_delta_ge_mmd=0.99,
        ci90_low=1.0,
    )
    assert state == BeliefState.INSUFFICIENT_EVIDENCE.value


def test_prospective_supported_requires_mmd_and_ci() -> None:
    state = classify_belief_state(
        phase=EvidencePhase.PROSPECTIVE_VALIDATION.value,
        n_sufficient=10,
        n_below=10,
        p_delta_gt_0=0.99,
        p_delta_ge_mmd=0.96,
        ci90_low=0.1,
    )
    assert state == BeliefState.PROSPECTIVE_SUPPORTED.value
    weak = classify_belief_state(
        phase=EvidencePhase.PROSPECTIVE_VALIDATION.value,
        n_sufficient=10,
        n_below=10,
        p_delta_gt_0=0.99,
        p_delta_ge_mmd=0.96,
        ci90_low=-0.1,  # CI crosses zero → not supported
    )
    assert weak != BeliefState.PROSPECTIVE_SUPPORTED.value


def test_credible_interval_ordered() -> None:
    seed = derive_seed("exp_ci", "1.0", "BASELINE_EXPLORATORY")
    result = bayesian_bootstrap_difference_in_means(
        sufficient=[7.0, 7.5, 8.0],
        below=[6.0, 6.5, 7.0],
        minimum_meaningful_difference=0.5,
        seed=seed,
        draws=2000,
    )
    assert result.credible_interval_90_low <= result.credible_interval_90_high
    assert result.credible_interval_95_low <= result.credible_interval_95_high
    assert 0.0 <= result.p_delta_gt_0 <= 1.0
