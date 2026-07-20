"""Wellbeing V2 canonical weights, decays, and domain caps.

Single source of truth for documentation in docs/wellbeing/*.md and
implementation in domain_packs/life/wellbeing_v2/.

Formula status SHADOW — wellbeing_v1 remains ACTIVE production default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

FORMULA_ID: Final = "wellbeing_v2"
FORMULA_VERSION: Final = "2.0.0"
FORMULA_STATUS: Final = "SHADOW"

TANH_TEMPERATURE: Final = 1.2
ACCUMULATION_RETENTION: Final = 0.72
ACUTE_CHRONIC_ANTICIPATORY: Final = (0.45, 0.40, 0.15)

HAPPINESS_WEIGHTS: Final = {
    "positive_affect": 0.22,
    "vitality": 0.14,
    "satisfaction": 0.10,
    "agency": 0.08,
    "connection": 0.12,
    "enjoyment": 0.08,
    "recovery": 0.14,
    "positive_anticipation": 0.06,
    "persistent_friction": 0.06,
}

STRESS_WEIGHTS: Final = {
    "cognitive": 0.18,
    "emotional": 0.20,
    "physiological": 0.18,
    "contextual": 0.12,
    "anticipatory": 0.10,
    "accumulated": 0.12,
    "recovery_deficit": 0.15,
    "protective_capacity": 0.05,
}

CONFIDENCE_WEIGHTS: Final = {
    "coverage": 0.18,
    "freshness": 0.14,
    "reliability": 0.12,
    "baseline_maturity": 0.14,
    "agreement": 0.10,
    "stability": 0.10,
    "calibration": 0.08,
    "missingness": 0.08,
    "inference": 0.04,
    "ood": 0.02,
}

OVERALL_CONFIDENCE_BLEND: Final = {
    "happiness_confidence": 0.35,
    "stress_confidence": 0.35,
    "cross_agreement": 0.15,
    "global_coverage": 0.15,
}

DOMAIN_CAPS: Final = {
    "sleep": {
        "max_total_contribution": 0.30,
        "sub_scores": ("recovery", "physiological", "recovery_deficit"),
    },
    "movement": {
        "max_total_contribution": 0.22,
        "sub_scores": ("vitality", "enjoyment", "protective_capacity"),
    },
    "cognitive": {
        "max_total_contribution": 0.28,
        "sub_scores": ("cognitive", "anticipatory"),
    },
    "affect": {
        "max_total_contribution": 0.25,
        "sub_scores": ("positive_affect", "emotional"),
    },
}


@dataclass(frozen=True)
class Weights:
    """Frozen bundle of all V2 weight tables."""

    happiness: dict[str, float]
    stress: dict[str, float]
    confidence: dict[str, float]
    overall_confidence_blend: dict[str, float]


WEIGHTS = Weights(
    happiness=dict(HAPPINESS_WEIGHTS),
    stress=dict(STRESS_WEIGHTS),
    confidence=dict(CONFIDENCE_WEIGHTS),
    overall_confidence_blend=dict(OVERALL_CONFIDENCE_BLEND),
)


@dataclass(frozen=True)
class Decays:
    """Feature half-life hours keyed by feature ID (see feature registry)."""

    checkin_happiness: float = 36.0
    checkin_energy: float = 24.0
    checkin_stress: float = 24.0
    checkin_productivity: float = 48.0
    checkin_sleep_hours: float = 72.0
    checkin_gym_done: float = 48.0
    checkin_social_activity: float = 72.0
    checkin_alcohol: float = 48.0
    checkin_meetings: float = 24.0
    workout_completed: float = 72.0
    task_overdue_count: float = 24.0
    task_completed_count: float = 48.0
    meeting_density: float = 12.0
    calendar_free_block_minutes: float = 12.0

    def as_dict(self) -> dict[str, float]:
        return {
            "checkin_happiness": self.checkin_happiness,
            "checkin_energy": self.checkin_energy,
            "checkin_stress": self.checkin_stress,
            "checkin_productivity": self.checkin_productivity,
            "checkin_sleep_hours": self.checkin_sleep_hours,
            "checkin_gym_done": self.checkin_gym_done,
            "checkin_social_activity": self.checkin_social_activity,
            "checkin_alcohol": self.checkin_alcohol,
            "checkin_meetings": self.checkin_meetings,
            "workout_completed": self.workout_completed,
            "task_overdue_count": self.task_overdue_count,
            "task_completed_count": self.task_completed_count,
            "meeting_density": self.meeting_density,
            "calendar_free_block_minutes": self.calendar_free_block_minutes,
        }


DECAYS = Decays()

COLD_START_MIN_DAYS: Final = 3
CALIBRATION_MIN_LABELS: Final = 20
