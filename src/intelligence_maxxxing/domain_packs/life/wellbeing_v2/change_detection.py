"""Change-state detection for wellbeing_v2."""

from __future__ import annotations

from intelligence_maxxxing.domain_packs.life.wellbeing_v2.happiness import HappinessResult
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.stress import StressResult


def detect_change_state(
    happiness: HappinessResult,
    stress: StressResult,
    *,
    sample_size: int,
) -> str:
    if sample_size < 3 or happiness.score is None or stress.score is None:
        return "INSUFFICIENT_EVIDENCE"
    h_trend = happiness.trend
    s_trend = stress.trend
    h_score = happiness.score
    s_score = stress.score
    if s_score >= 70 and stress.chronic is not None and stress.chronic >= 60:
        return "PERSISTENT_LOAD"
    if s_score >= 62 and s_trend in {"rising", "stable"} and h_score <= 55:
        return "RISING_STRESS"
    if h_trend == "falling" and s_score >= (stress.baseline or 50):
        return "FALLING_HAPPINESS"
    if s_score < 45 and s_trend == "falling" and h_trend in {"rising", "stable"}:
        return "RECOVERING"
    if h_trend == "rising" and s_score < 55:
        return "POSITIVE_SHIFT"
    if h_trend == "falling" or s_trend == "rising":
        return "NEGATIVE_SHIFT"
    return "STABLE"
