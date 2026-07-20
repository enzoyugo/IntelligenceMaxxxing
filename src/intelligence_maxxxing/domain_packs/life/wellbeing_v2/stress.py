"""Hierarchical Stress Load V2 with accumulation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from intelligence_maxxxing.domain_packs.life.wellbeing_v2.features import FeatureBundle
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.math_utils import clamp, tanh_map
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.registry import (
    ACUTE_CHRONIC_ANTICIPATORY,
    STRESS_WEIGHTS,
    TANH_TEMPERATURE,
)


def _v(signals: dict[str, float | None], key: str, default: float = 0.0) -> float:
    val = signals.get(key)
    return float(val) if val is not None else default


@dataclass(frozen=True)
class StressResult:
    score: float | None
    latent: float | None
    acute: float | None
    chronic: float | None
    anticipatory: float | None
    baseline: float | None
    trend: str
    sub_scores: dict[str, float]
    contributors: list[dict[str, Any]]
    protective_factors: list[dict[str, Any]]


def compose_stress(features: FeatureBundle) -> StressResult:
    s = features.signals
    cognitive = clamp(0.7 * _v(s, "meetings_n") + 0.3 * max(0.0, _v(s, "productivity_rz")))
    emotional = clamp(_v(s, "stress_rz", _v(s, "stress_raw")))
    physiological = clamp(
        0.5 * max(0.0, -_v(s, "sleep_rz"))
        + 0.3 * _v(s, "sleep_debt_n")
        + 0.2 * _v(s, "consec_short_sleep_n")
        + 0.15 * _v(s, "alcohol")
    )
    contextual = clamp(0.6 * _v(s, "meetings_n") + 0.4 * _v(s, "load_n"))
    anticipatory = clamp(0.8 * _v(s, "meetings_n") + 0.2 * cognitive)  # calendar-lite proxy
    accumulated = clamp(_v(s, "load_n"))
    recovery_deficit = clamp(
        0.5 * _v(s, "sleep_debt_n")
        + 0.3 * max(0.0, -_v(s, "energy_rz"))
        + 0.2 * (1.0 - _v(s, "gym", 0.0))
    )
    protective = clamp(
        0.4 * max(0.0, _v(s, "sleep_rz"))
        + 0.3 * _v(s, "social")
        + 0.2 * _v(s, "gym")
        + 0.1 * max(0.0, _v(s, "energy_rz"))
    )

    # Cap physiological (sleep family) so short sleep features don't triple-count
    phys_cap = 0.85
    physiological = min(physiological, phys_cap)

    subs = {
        "cognitive": cognitive,
        "emotional": emotional,
        "physiological": physiological,
        "contextual": contextual,
        "anticipatory": anticipatory,
        "accumulated": accumulated,
        "recovery_deficit": recovery_deficit,
        "protective_capacity": protective,
    }

    domain_latent = (
        STRESS_WEIGHTS["cognitive"] * cognitive
        + STRESS_WEIGHTS["emotional"] * emotional
        + STRESS_WEIGHTS["physiological"] * physiological
        + STRESS_WEIGHTS["contextual"] * contextual
        + STRESS_WEIGHTS["anticipatory"] * anticipatory
        + STRESS_WEIGHTS["accumulated"] * accumulated
        + STRESS_WEIGHTS["recovery_deficit"] * recovery_deficit
        - STRESS_WEIGHTS["protective_capacity"] * protective
    )

    # Interaction low sleep × high workload
    domain_latent = domain_latent + max(0.0, physiological) * max(0.0, cognitive) * 0.15
    domain_latent = clamp(domain_latent, -0.5, 2.8)

    w_a, w_c, w_ant = ACUTE_CHRONIC_ANTICIPATORY
    acute_l = clamp(0.55 * emotional + 0.45 * cognitive)
    chronic_l = clamp(0.5 * accumulated + 0.5 * recovery_deficit)
    ant_l = anticipatory
    latent = w_a * acute_l + w_c * chronic_l + w_ant * ant_l
    # Blend domain composition with temporal mix
    latent = clamp(0.55 * domain_latent + 0.45 * latent, -0.5, 2.8)

    score = tanh_map(latent, TANH_TEMPERATURE)
    acute = tanh_map(acute_l, TANH_TEMPERATURE)
    chronic = tanh_map(chronic_l, TANH_TEMPERATURE)
    anticipatory_score = tanh_map(ant_l, TANH_TEMPERATURE)

    base_s = features.baselines.get("stress_median")
    baseline = None
    if base_s is not None:
        baseline = round(clamp(50.0 + (float(base_s) - 5.5) / 4.5 * 50.0, 0.0, 100.0), 2)

    trend = "stable"
    if score is not None and baseline is not None:
        if score > baseline + 7:
            trend = "rising"
        elif score < baseline - 7:
            trend = "falling"

    if features.sample_size < 3 and score is not None:
        score = min(score, 82.0)
        score = max(score, 18.0)

    contributors: list[dict[str, Any]] = []
    protectors: list[dict[str, Any]] = []
    for name, weight in STRESS_WEIGHTS.items():
        val = subs[name]
        if name == "protective_capacity":
            protectors.append(
                {
                    "domain": "stress",
                    "feature": name,
                    "effect_points": round(-weight * val * 50.0, 2),
                    "direction": "decrease_stress",
                    "reliability": 0.7,
                    "observed": True,
                    "sub_score": round(val, 3),
                }
            )
            continue
        effect = weight * val * 50.0
        contributors.append(
            {
                "domain": "stress",
                "feature": name,
                "effect_points": round(effect, 2),
                "direction": "increase_stress",
                "reliability": 0.8,
                "observed": True,
                "sub_score": round(val, 3),
                "evidence": {
                    "load_state": round(features.load_state, 3),
                    "sleep_debt_3d": features.sleep_debt_3d,
                },
            }
        )
    contributors.sort(key=lambda c: abs(float(c["effect_points"])), reverse=True)

    if features.sample_size == 0:
        return StressResult(
            score=None,
            latent=None,
            acute=None,
            chronic=None,
            anticipatory=None,
            baseline=baseline,
            trend="insufficient_evidence",
            sub_scores=subs,
            contributors=[],
            protective_factors=[],
        )

    return StressResult(
        score=score,
        latent=round(latent, 4),
        acute=acute,
        chronic=chronic,
        anticipatory=anticipatory_score,
        baseline=baseline,
        trend=trend,
        sub_scores={k: round(v, 4) for k, v in subs.items()},
        contributors=contributors[:8],
        protective_factors=protectors,
    )
