"""Bayesian Bootstrap Difference in Means v1.

Deterministic, seedable, dependency: numpy only.
Estimand: mean(productivity | SUFFICIENT) - mean(productivity | BELOW_THRESHOLD).

Does NOT claim causality. Does NOT produce recommendations.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

METHOD_ID = "BayesianBootstrapDifferenceInMeans.v1"
DEFAULT_DRAWS = 20_000


@dataclass(frozen=True)
class BootstrapResult:
    method: str
    draws: int
    seed: str
    posterior_median_delta: float
    posterior_mean_delta: float
    credible_interval_90_low: float
    credible_interval_90_high: float
    credible_interval_95_low: float
    credible_interval_95_high: float
    p_delta_gt_0: float
    p_delta_ge_mmd: float
    mean_sufficient: float
    mean_below: float
    n_sufficient: int
    n_below: int


def derive_seed(experiment_id: str, protocol_version: str, phase: str) -> str:
    """Deterministic seed material from experiment identity + phase."""
    material = f"{experiment_id}|{protocol_version}|{phase}|{METHOD_ID}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _seed_to_int(seed_hex: str) -> int:
    # Use 63 bits so it fits a non-negative int64 SeedSequence space.
    return int(seed_hex[:16], 16) & 0x7FFFFFFFFFFFFFFF


def bayesian_bootstrap_difference_in_means(
    *,
    sufficient: list[float],
    below: list[float],
    minimum_meaningful_difference: float,
    seed: str,
    draws: int = DEFAULT_DRAWS,
) -> BootstrapResult:
    """Dirichlet-weighted bootstrap of the difference in group means.

    Requires both groups non-empty. Raises ValueError otherwise.
    """
    if not sufficient or not below:
        raise ValueError("both exposure groups must be non-empty for the bootstrap")
    if draws < 100:
        raise ValueError("draws must be >= 100")

    rng = np.random.default_rng(_seed_to_int(seed))
    suf = np.asarray(sufficient, dtype=np.float64)
    bel = np.asarray(below, dtype=np.float64)

    # Dirichlet(1,...,1) == uniform on the simplex → Bayesian bootstrap weights.
    w_suf = rng.dirichlet(np.ones(len(suf)), size=draws)
    w_bel = rng.dirichlet(np.ones(len(bel)), size=draws)
    deltas = (w_suf @ suf) - (w_bel @ bel)

    p90_low, p90_high = np.percentile(deltas, [5.0, 95.0])
    p95_low, p95_high = np.percentile(deltas, [2.5, 97.5])

    return BootstrapResult(
        method=METHOD_ID,
        draws=draws,
        seed=seed,
        posterior_median_delta=float(np.median(deltas)),
        posterior_mean_delta=float(np.mean(deltas)),
        credible_interval_90_low=float(p90_low),
        credible_interval_90_high=float(p90_high),
        credible_interval_95_low=float(p95_low),
        credible_interval_95_high=float(p95_high),
        p_delta_gt_0=float(np.mean(deltas > 0.0)),
        p_delta_ge_mmd=float(np.mean(deltas >= minimum_meaningful_difference)),
        mean_sufficient=float(np.mean(suf)),
        mean_below=float(np.mean(bel)),
        n_sufficient=len(suf),
        n_below=len(bel),
    )


def classify_belief_state(
    *,
    phase: str,
    n_sufficient: int,
    n_below: int,
    p_delta_gt_0: float,
    p_delta_ge_mmd: float,
    ci90_low: float,
    minimum_group_size_exploratory: int = 5,
    minimum_total_exploratory: int = 14,
    minimum_group_size_prospective: int = 7,
    expired: bool = False,
    prospective_target: int | None = None,
    critical_data_quality_failure: bool = False,
) -> str:
    """Map bootstrap outputs to a BeliefState value (string for catalog payloads).

    Stage 3.1: prospective terminal states require prospective_target and group
    minima. Strong effects cannot bypass an incomplete target.
    """
    from intelligence_maxxxing.domain.common.epistemic import BeliefState, EvidencePhase

    total = n_sufficient + n_below
    if phase == EvidencePhase.BASELINE_EXPLORATORY.value:
        if (
            total < minimum_total_exploratory
            or n_sufficient < minimum_group_size_exploratory
            or n_below < minimum_group_size_exploratory
        ):
            return BeliefState.INSUFFICIENT_EVIDENCE.value
        if p_delta_gt_0 >= 0.80:
            return BeliefState.EXPLORATORY_POSITIVE.value
        if (1.0 - p_delta_gt_0) >= 0.80:  # P(delta <= 0)
            return BeliefState.EXPLORATORY_NEGATIVE.value
        return BeliefState.EXPLORATORY_INCONCLUSIVE.value

    if phase == EvidencePhase.PROSPECTIVE_VALIDATION.value:
        if critical_data_quality_failure:
            # Block support; still collecting or expire separately.
            if expired:
                return BeliefState.EXPIRED_INCONCLUSIVE.value
            return BeliefState.PROSPECTIVE_COLLECTING.value

        target = prospective_target if prospective_target is not None else 0
        target_met = total >= target
        groups_met = (
            n_sufficient >= minimum_group_size_prospective
            and n_below >= minimum_group_size_prospective
        )

        if expired and not (target_met and groups_met):
            return BeliefState.EXPIRED_INCONCLUSIVE.value

        if not target_met or not groups_met:
            # Strong effect cannot early-stop before target/groups.
            return BeliefState.PROSPECTIVE_COLLECTING.value

        if p_delta_ge_mmd >= 0.95 and ci90_low > 0.0:
            return BeliefState.PROSPECTIVE_SUPPORTED.value
        if (1.0 - p_delta_gt_0) >= 0.95:  # P(delta <= 0)
            return BeliefState.PROSPECTIVE_WEAKENED.value
        return BeliefState.PROSPECTIVE_INCONCLUSIVE.value

    raise ValueError(f"unknown evidence phase: {phase!r}")
