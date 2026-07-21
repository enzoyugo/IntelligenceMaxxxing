"""Deterministic math helpers for wellbeing_v2 (no numpy required)."""

from __future__ import annotations

import math
from statistics import median


def clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def clamp100(value: float) -> float:
    return max(0.0, min(100.0, value))


def tanh_map(latent: float, temperature: float = 1.2) -> float:
    """Map latent ≈ [-∞,∞] to [0,100] via 50 + 50*tanh(latent/T)."""
    t = max(temperature, 1e-6)
    return round(clamp100(50.0 + 50.0 * math.tanh(latent / t)), 2)


def scale_1_10(value: float | None) -> float | None:
    """Legacy helper for Likert authoring in tests only — not used on productive paths."""
    if value is None:
        return None
    return clamp((float(value) - 5.5) / 4.5, -1.0, 1.0)


def scale_0_100(value: float | None) -> float | None:
    """Map canonical 0–100 score to composition signal [-1, 1]."""
    if value is None:
        return None
    return clamp((float(value) - 50.0) / 50.0, -1.0, 1.0)


def mad(values: list[float]) -> float:
    if not values:
        return 0.0
    m = median(values)
    return median([abs(v - m) for v in values])


def robust_z(current: float, history: list[float], epsilon: float = 0.25) -> float:
    if len(history) < 2:
        return 0.0
    m = median(history)
    scale = max(1.4826 * mad(history), epsilon)
    return clamp((current - m) / scale, -3.5, 3.5)


def baseline_maturity(n: int) -> str:
    if n <= 2:
        return "NO_BASELINE"
    if n <= 6:
        return "EMERGING"
    if n <= 20:
        return "USABLE"
    if n <= 59:
        return "MATURE"
    return "STABLE"


def maturity_score(n: int) -> float:
    """Map maturity to [0,1] for confidence."""
    labels = {
        "NO_BASELINE": 0.05,
        "EMERGING": 0.25,
        "USABLE": 0.55,
        "MATURE": 0.8,
        "STABLE": 0.95,
    }
    return labels[baseline_maturity(n)]


def exp_decay(effect: float, elapsed_hours: float, half_life_hours: float) -> float:
    if half_life_hours <= 0:
        return effect
    return effect * math.exp(-elapsed_hours * math.log(2) / half_life_hours)


def mean_or_none(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None
