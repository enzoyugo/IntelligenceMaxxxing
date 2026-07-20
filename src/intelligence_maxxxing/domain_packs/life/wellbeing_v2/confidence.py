"""Multi-component Confidence Score V2 (evidence quality, not certainty)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from intelligence_maxxxing.domain_packs.life.wellbeing_v2.features import FeatureBundle
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.math_utils import (
    clamp100,
    maturity_score,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.registry import (
    CALIBRATION_MIN_LABELS,
    CONFIDENCE_WEIGHTS,
    OVERALL_CONFIDENCE_BLEND,
)


@dataclass(frozen=True)
class ConfidenceResult:
    overall: float
    happiness_confidence: float
    stress_confidence: float
    components: dict[str, float]
    calibration_status: str
    plausible_happiness: tuple[float, float] | None
    plausible_stress: tuple[float, float] | None
    explanation: dict[str, Any]


def _coverage(features: FeatureBundle) -> float:
    domains = ("subjective", "sleep", "schedule", "activity", "tasks")
    weights = {"subjective": 0.3, "sleep": 0.25, "schedule": 0.2, "activity": 0.15, "tasks": 0.1}
    score = 0.0
    for d in domains:
        if d in features.observed_domains:
            score += weights[d]
    return min(1.0, score)


def compose_confidence(
    features: FeatureBundle,
    *,
    happiness_score: float | None,
    stress_score: float | None,
    label_count: int = 0,
) -> ConfidenceResult:
    coverage = _coverage(features)
    # Freshness: denser recent window → higher
    freshness = min(1.0, features.sample_size / max(features.window_days * 0.7, 1))
    reliability = 0.85 if "subjective" in features.observed_domains else 0.45
    baseline_m = (
        maturity_score(int(features.baselines.get("n_happiness") or 0))
        + maturity_score(int(features.baselines.get("n_stress") or 0))
        + maturity_score(int(features.baselines.get("n_sleep") or 0))
    ) / 3.0

    # Agreement: stress high with low energy/sleep vs contradiction
    s = features.signals
    stress_sig = s.get("stress_rz") or s.get("stress_raw") or 0.0
    energy_sig = s.get("energy_rz") or 0.0
    sleep_sig = s.get("sleep_rz") or 0.0
    if stress_sig > 0.3 and energy_sig < 0 and sleep_sig < 0:
        agreement = 0.85
    elif stress_sig > 0.4 and energy_sig > 0.3 and sleep_sig > 0.2:
        agreement = 0.35  # conflict
    else:
        agreement = 0.65

    stability = 0.7 if features.sample_size >= 5 else 0.4
    if label_count >= CALIBRATION_MIN_LABELS:
        calibration = 0.7
        cal_status = "OFFSET_SCALE_ELIGIBLE"
    elif label_count >= 7:
        calibration = 0.45
        cal_status = "OFFSET_ONLY"
    else:
        calibration = 0.2
        cal_status = "UNCALIBRATED"

    missingness = min(1.0, features.missing_days / max(features.window_days, 1))
    inference = 0.3 if features.overdue_proxy is not None and "tasks" not in features.observed_domains else 0.1
    ood = 0.4 if features.load_state > 2.8 else 0.1

    comps = {
        "coverage": coverage,
        "freshness": freshness,
        "reliability": reliability,
        "baseline_maturity": baseline_m,
        "agreement": agreement,
        "stability": stability,
        "calibration": calibration,
        "missingness": 1.0 - missingness,
        "inference": 1.0 - inference,
        "ood": 1.0 - ood,
    }

    raw = sum(CONFIDENCE_WEIGHTS[k] * comps[k] for k in CONFIDENCE_WEIGHTS)
    overall = round(clamp100(raw * 100.0), 2)

    # Asymmetric confidences
    h_cov = 1.0 if "subjective" in features.observed_domains else 0.35
    s_cov = 1.0 if ("subjective" in features.observed_domains or "schedule" in features.observed_domains) else 0.4
    happiness_c = round(clamp100(overall * (0.55 + 0.45 * h_cov) * (0.7 + 0.3 * comps["freshness"])), 2)
    stress_c = round(clamp100(overall * (0.55 + 0.45 * s_cov) * (0.75 + 0.25 * comps["baseline_maturity"])), 2)

    blend = OVERALL_CONFIDENCE_BLEND
    overall = round(
        clamp100(
            blend["happiness_confidence"] * happiness_c
            + blend["stress_confidence"] * stress_c
            + blend["cross_agreement"] * agreement * 100
            + blend["global_coverage"] * coverage * 100
        ),
        2,
    )

    # Plausible ranges widen when confidence low
    def rng(score: float | None, conf: float) -> tuple[float, float] | None:
        if score is None:
            return None
        half = max(4.0, (100.0 - conf) * 0.22)
        return (round(max(0.0, score - half), 1), round(min(100.0, score + half), 1))

    # Guardrail: never high confidence with empty/minimal data
    if features.sample_size < 3:
        overall = min(overall, 28.0)
        happiness_c = min(happiness_c, 24.0)
        stress_c = min(stress_c, 26.0)

    return ConfidenceResult(
        overall=overall,
        happiness_confidence=happiness_c,
        stress_confidence=stress_c,
        components={k: round(v, 3) for k, v in comps.items()},
        calibration_status=cal_status,
        plausible_happiness=rng(happiness_score, happiness_c),
        plausible_stress=rng(stress_score, stress_c),
        explanation={
            "definition": "Evidence quality for the estimate — not clinical certainty.",
            "calibration_status": cal_status,
            "label_count": label_count,
            "note": "UNCALIBRATED until sufficient posterior feedback labels.",
        },
    )
