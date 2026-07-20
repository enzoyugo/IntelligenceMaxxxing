"""Deterministic learning-text templates (no LLM)."""

from intelligence_maxxxing.domain.common.epistemic import (
    AgreementWithPrior,
    BeliefState,
    LearningChangeType,
)


def learning_texts(
    *,
    agreement: AgreementWithPrior,
    prior_state: BeliefState | None,
    new_state: BeliefState,
    prior_p: float | None,
    new_p: float,
) -> tuple[LearningChangeType, str, str, str, str]:
    """Return (change_type, what_changed, why_changed, remains_unknown, next_needed)."""
    prior_label = prior_state.value if prior_state else "none"
    if agreement is AgreementWithPrior.NOT_COMPARABLE or prior_state is None:
        change = LearningChangeType.FIRST_PROSPECTIVE
        what = (
            f"A prospective belief was formed with state {new_state.value}. "
            f"No comparable exploratory prior was available."
        )
        why = "Prospective validation completed without a prior exploratory belief to compare."
    elif agreement is AgreementWithPrior.STRENGTHENED:
        change = LearningChangeType.PRIOR_STRENGTHENED
        what = (
            f"The prospective cohort strengthened the prior belief "
            f"({prior_label} → {new_state.value})."
        )
        why = _p_change(prior_p, new_p)
    elif agreement is AgreementWithPrior.WEAKENED:
        change = LearningChangeType.PRIOR_WEAKENED
        what = (
            f"The prospective cohort produced weaker evidence than the exploratory baseline "
            f"({prior_label} → {new_state.value})."
        )
        why = _p_change(prior_p, new_p)
    elif agreement is AgreementWithPrior.CONTRADICTED:
        change = LearningChangeType.PRIOR_CONTRADICTED
        what = (
            f"The prospective cohort contradicted the exploratory baseline "
            f"({prior_label} → {new_state.value})."
        )
        why = _p_change(prior_p, new_p)
    elif new_state is BeliefState.EXPIRED_INCONCLUSIVE:
        change = LearningChangeType.EXPIRED
        what = "The prospective window expired before both exposure groups reached minimum size."
        why = "Stopping rule: maximum_window_days elapsed with incomplete cohort balance."
    else:
        change = LearningChangeType.FIRST_PROSPECTIVE
        what = f"Belief state is now {new_state.value} (prior {prior_label})."
        why = _p_change(prior_p, new_p)

    remains = (
        "Causal direction is unknown. Unmeasured confounding may remain. "
        "Calibration is UNCALIBRATED."
    )
    next_needed = (
        "Additional independent prospective check-ins under the same pre-registered "
        "protocol, or a retired-and-repreregistered protocol if parameters must change."
    )
    return change, what, why, remains, next_needed


def _p_change(prior_p: float | None, new_p: float) -> str:
    if prior_p is None:
        return f"The model probability of a positive difference is {new_p:.3f}."
    return f"The probability of a positive difference changed from {prior_p:.3f} to {new_p:.3f}."


def agreement_with_prior(prior: BeliefState | None, new: BeliefState) -> AgreementWithPrior:
    if prior is None:
        return AgreementWithPrior.NOT_COMPARABLE
    positive = {
        BeliefState.EXPLORATORY_POSITIVE,
        BeliefState.PROSPECTIVE_SUPPORTED,
    }
    negative = {
        BeliefState.EXPLORATORY_NEGATIVE,
        BeliefState.PROSPECTIVE_WEAKENED,
    }
    if prior in positive and new in positive:
        if new is BeliefState.PROSPECTIVE_SUPPORTED:
            return AgreementWithPrior.STRENGTHENED
        return AgreementWithPrior.UNCHANGED
    if prior in negative and new in negative:
        return AgreementWithPrior.STRENGTHENED
    if prior in positive and new in negative:
        return AgreementWithPrior.CONTRADICTED
    if prior in negative and new in positive:
        return AgreementWithPrior.CONTRADICTED
    if prior in positive and new is BeliefState.PROSPECTIVE_INCONCLUSIVE:
        return AgreementWithPrior.WEAKENED
    if new is BeliefState.EXPIRED_INCONCLUSIVE:
        return AgreementWithPrior.NOT_COMPARABLE
    return AgreementWithPrior.UNCHANGED
