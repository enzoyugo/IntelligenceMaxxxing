"""Eligibility selection for life.sleep_threshold_productivity.v1.

Reads ONLY public observation projection rows (no direct table access from
callers). Never imputes. Every exclusion is counted by reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

TEMPLATE_ID = "life.sleep_threshold_productivity.v1"
TEMPLATE_VERSION = "1.0"
LIFE_EVENT_TYPE = "life.daily_check_in.completed.v1"
HYPOTHESIS_STATEMENT = (
    "Daily check-ins with sleep_hours greater than or equal to the "
    "human-confirmed threshold are associated with higher productivity "
    "than daily check-ins below that threshold for this subject."
)
OBSERVATIONAL_LIMITATION = "This is an observational association and may reflect confounding."
ANALYSIS_METHOD = "BayesianBootstrapDifferenceInMeans.v1"
RANDOM_SEED_POLICY = "sha256(experiment_id|protocol_version|phase|method)"


@dataclass
class EligibleObservation:
    observation_id: str
    event_id: str
    occurred_at: datetime
    sleep_hours: float
    productivity: float
    attributes: dict[str, Any]


@dataclass
class EligibilityResult:
    eligible: list[EligibleObservation] = field(default_factory=list)
    excluded_count: int = 0
    exclusion_reasons: dict[str, int] = field(default_factory=dict)

    def _exclude(self, reason: str) -> None:
        self.excluded_count += 1
        self.exclusion_reasons[reason] = self.exclusion_reasons.get(reason, 0) + 1


def _attrs(context: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(context, dict):
        return {}
    attributes = context.get("attributes")
    return attributes if isinstance(attributes, dict) else {}


def select_eligible_checkins(
    rows: list[Any],
    *,
    tenant_id: str,
    owner_id: str,
    application_id: str,
) -> EligibilityResult:
    """Filter projected observations into eligible daily check-ins.

    `rows` are ProjectedObservation-like objects with attributes:
    observation_id, event_id, tenant_id, owner_id, application_id,
    domain_pack, subject, knowledge_class, metadata, context, occurred_at.
    """
    result = EligibilityResult()
    seen_sources: set[str] = set()

    for row in rows:
        if (
            row.tenant_id != tenant_id
            or row.owner_id != owner_id
            or row.application_id != application_id
        ):
            result._exclude("other_scope")
            continue
        if row.domain_pack != "life":
            result._exclude("wrong_domain_pack")
            continue
        if row.subject != "daily_check_in":
            result._exclude("wrong_subject")
            continue
        if row.knowledge_class != "OBSERVED_FACT":
            result._exclude("wrong_knowledge_class")
            continue
        meta = row.metadata if isinstance(row.metadata, dict) else {}
        if meta.get("life_event_type") != LIFE_EVENT_TYPE:
            result._exclude("wrong_event_type")
            continue
        if row.occurred_at is None:
            result._exclude("missing_occurred_at")
            continue
        attrs = _attrs(row.context if isinstance(row.context, dict) else {})
        sleep = attrs.get("sleep_hours")
        productivity = attrs.get("productivity")
        if sleep is None or productivity is None:
            result._exclude("missing_required_fields")
            continue
        try:
            sleep_f = float(sleep)
            prod_f = float(productivity)
        except (TypeError, ValueError):
            result._exclude("invalid_values")
            continue
        if not (0.0 <= sleep_f <= 24.0):
            result._exclude("invalid_sleep_hours")
            continue
        if not (1.0 <= prod_f <= 10.0):
            result._exclude("invalid_productivity")
            continue
        # Deduplicate by observation_id (source of truth for one check-in day).
        if row.observation_id in seen_sources:
            result._exclude("duplicate_source")
            continue
        seen_sources.add(row.observation_id)
        result.eligible.append(
            EligibleObservation(
                observation_id=row.observation_id,
                event_id=row.event_id,
                occurred_at=row.occurred_at,
                sleep_hours=sleep_f,
                productivity=prod_f,
                attributes=attrs,
            )
        )
    return result


def split_by_cutoff(
    eligible: list[EligibleObservation],
    *,
    baseline_cutoff: datetime,
    prospective_start: datetime,
) -> tuple[list[EligibleObservation], list[EligibleObservation]]:
    """Baseline: occurred_at < cutoff. Prospective: occurred_at >= prospective_start.

    Observations in [cutoff, prospective_start) if any are excluded from both
    (should not happen when cutoff == prospective_start).
    """
    baseline = [o for o in eligible if o.occurred_at < baseline_cutoff]
    prospective = [o for o in eligible if o.occurred_at >= prospective_start]
    return baseline, prospective


def partition_exposure(
    cohort: list[EligibleObservation], threshold: float
) -> tuple[list[EligibleObservation], list[EligibleObservation]]:
    sufficient = [o for o in cohort if o.sleep_hours >= threshold]
    below = [o for o in cohort if o.sleep_hours < threshold]
    return sufficient, below


CONFOUNDING_VARS = (
    "stress",
    "alcohol",
    "meetings_count",
    "gym_done",
    "football_played",
    "social_activity",
)


def confounding_diagnostics(
    sufficient: list[EligibleObservation],
    below: list[EligibleObservation],
) -> list[dict[str, Any]]:
    """Descriptive imbalance diagnostics. Never claims confounding was corrected."""
    out: list[dict[str, Any]] = []
    for var in CONFOUNDING_VARS:
        s_vals = [_num(o.attributes.get(var)) for o in sufficient]
        b_vals = [_num(o.attributes.get(var)) for o in below]
        s_present = [v for v in s_vals if v is not None]
        b_present = [v for v in b_vals if v is not None]
        s_mean = sum(s_present) / len(s_present) if s_present else None
        b_mean = sum(b_present) / len(b_present) if b_present else None
        abs_diff = abs(s_mean - b_mean) if s_mean is not None and b_mean is not None else None
        s_miss = 1.0 - (len(s_present) / len(sufficient)) if sufficient else 1.0
        b_miss = 1.0 - (len(b_present) / len(below)) if below else 1.0
        # Material imbalance heuristic: |diff| >= 1.0 on a 0-10-ish scale, or
        # 0.25 absolute for boolean-ish proportions.
        potential = False
        if abs_diff is not None:
            potential = abs_diff >= (
                0.25
                if var in {"alcohol", "gym_done", "football_played", "social_activity"}
                else 1.0
            )
        out.append(
            {
                "variable": var,
                "sufficient_n": len(s_present),
                "below_n": len(b_present),
                "sufficient_mean_or_proportion": s_mean,
                "below_mean_or_proportion": b_mean,
                "absolute_difference": abs_diff,
                "missingness_sufficient": s_miss,
                "missingness_below": b_miss,
                "potential_confounding": potential,
            }
        )
    return out


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
