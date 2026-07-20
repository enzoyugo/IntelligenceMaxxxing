"""Hierarchical Happiness Score V2 composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from intelligence_maxxxing.domain_packs.life.wellbeing_v2.features import FeatureBundle
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.math_utils import clamp, tanh_map
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.registry import (
    HAPPINESS_WEIGHTS,
    TANH_TEMPERATURE,
)


def _v(signals: dict[str, float | None], key: str, default: float = 0.0) -> float:
    val = signals.get(key)
    return float(val) if val is not None else default


@dataclass(frozen=True)
class HappinessResult:
    score: float | None
    latent: float | None
    acute: float | None
    chronic: float | None
    baseline: float | None
    trend: str
    sub_scores: dict[str, float]
    contributors: list[dict[str, Any]]


def compose_happiness(features: FeatureBundle) -> HappinessResult:
    s = features.signals
    # Sub-scores on [-1, 1]
    positive_affect = _v(s, "happiness_rz", _v(s, "happiness_raw"))
    vitality = 0.7 * _v(s, "energy_rz") + 0.3 * (1.0 if _v(s, "gym", 0.0) > 0.5 else -0.1)
    vitality = clamp(vitality)
    satisfaction = clamp(0.6 * positive_affect + 0.4 * _v(s, "productivity_rz"))
    agency = clamp(_v(s, "productivity_rz") * 0.8 + (_v(s, "gym", 0.0) - 0.3) * 0.2)
    # Absence of social/gym is neutral (0), not a strong negative — only presence boosts
    social_boost = 0.55 if _v(s, "social", 0.0) > 0.5 else 0.0
    gym_boost = 0.35 if _v(s, "gym", 0.0) > 0.5 else 0.0
    connection = clamp(0.55 * positive_affect + social_boost)
    enjoyment = clamp(0.45 * positive_affect + 0.35 * social_boost + gym_boost)
    recovery = clamp(_v(s, "sleep_rz") - 0.5 * _v(s, "sleep_debt_n") - 0.3 * _v(s, "consec_short_sleep_n"))
    positive_anticipation = clamp(0.3 * connection + 0.2 * agency)  # weak without calendar positives
    persistent_friction = clamp(
        0.4 * _v(s, "stress_rz", _v(s, "stress_raw"))
        + 0.3 * _v(s, "load_n")
        + 0.3 * _v(s, "meetings_n")
    )

    subs = {
        "positive_affect": positive_affect,
        "vitality": vitality,
        "satisfaction": satisfaction,
        "agency": agency,
        "connection": connection,
        "enjoyment": enjoyment,
        "recovery": recovery,
        "positive_anticipation": positive_anticipation,
        "persistent_friction": persistent_friction,
    }

    # Domain cap: sleep-linked recovery contribution limited
    recovery_capped = clamp(recovery, -HAPPINESS_WEIGHTS["recovery"] * 3, HAPPINESS_WEIGHTS["recovery"] * 3)

    friction = max(0.0, persistent_friction)
    # Eustress: high affect+vitality with load should not crush Happiness
    if positive_affect > 0.25 and vitality > 0.15:
        friction *= 0.4

    latent = (
        HAPPINESS_WEIGHTS["positive_affect"] * positive_affect
        + HAPPINESS_WEIGHTS["vitality"] * vitality
        + HAPPINESS_WEIGHTS["satisfaction"] * satisfaction
        + HAPPINESS_WEIGHTS["agency"] * agency
        + HAPPINESS_WEIGHTS["connection"] * connection
        + HAPPINESS_WEIGHTS["enjoyment"] * enjoyment
        + HAPPINESS_WEIGHTS["recovery"] * recovery_capped
        + HAPPINESS_WEIGHTS["positive_anticipation"] * positive_anticipation
        - HAPPINESS_WEIGHTS["persistent_friction"] * friction
    )

    # Interaction: low sleep × high load (limited)
    sleep_workload = max(0.0, -recovery) * max(0.0, _v(s, "load_n")) * 0.12
    latent = clamp(latent - sleep_workload, -2.5, 2.5)

    score = tanh_map(latent, TANH_TEMPERATURE)

    # Acute ≈ latest affect/vitality; chronic ≈ satisfaction/recovery history proxy
    acute_latent = 0.6 * positive_affect + 0.4 * vitality
    chronic_latent = 0.5 * satisfaction + 0.5 * recovery
    acute = tanh_map(acute_latent, TANH_TEMPERATURE)
    chronic = tanh_map(chronic_latent, TANH_TEMPERATURE)

    base_h = features.baselines.get("happiness_median")
    baseline = None
    if base_h is not None:
        baseline = round(clamp(50.0 + (float(base_h) - 5.5) / 4.5 * 50.0, 0.0, 100.0), 2)

    trend = "stable"
    if score is not None and baseline is not None:
        if score < baseline - 6:
            trend = "falling"
        elif score > baseline + 6:
            trend = "rising"

    # Guardrail: single positive event can't push to 95+ without coverage
    if features.sample_size < 3 and score is not None:
        score = min(score, 78.0)
        score = max(score, 22.0)

    contributors: list[dict[str, Any]] = []
    for name, weight in HAPPINESS_WEIGHTS.items():
        val = subs[name]
        effect = weight * val * 50.0  # rough points on 0-100 scale
        if name == "persistent_friction":
            effect = -abs(effect) if val > 0 else 0.0
        contributors.append(
            {
                "domain": "happiness",
                "feature": name,
                "effect_points": round(effect, 2),
                "direction": "increase_happiness" if effect >= 0 else "decrease_happiness",
                "reliability": 0.85 if name in features.observed_domains or name == "positive_affect" else 0.55,
                "observed": name
                in {
                    "positive_affect",
                    "vitality",
                    "recovery",
                    "connection",
                    "agency",
                },
                "sub_score": round(val, 3),
            }
        )
    contributors.sort(key=lambda c: abs(float(c["effect_points"])), reverse=True)

    if features.sample_size == 0:
        return HappinessResult(
            score=None,
            latent=None,
            acute=None,
            chronic=None,
            baseline=baseline,
            trend="insufficient_evidence",
            sub_scores=subs,
            contributors=[],
        )

    return HappinessResult(
        score=score,
        latent=round(latent, 4),
        acute=acute,
        chronic=chronic,
        baseline=baseline,
        trend=trend,
        sub_scores={k: round(v, 4) for k, v in subs.items()},
        contributors=contributors[:8],
    )
