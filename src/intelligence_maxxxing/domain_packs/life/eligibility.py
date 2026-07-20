"""Eligibility selection for life.sleep_threshold_productivity.v1 (Stage 3.1).

Reads ONLY public observation projection rows. Deduplicates by logical source
identity (not observation_id). Temporal cohort membership uses activation and
evidence-cutoff anchors — never client clock alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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

SOURCE_ID_PREFIX = "lifemaxxxing://daily-check-ins/"
SOURCE_ID_RE = re.compile(r"^lifemaxxxing://daily-check-ins/([A-Za-z0-9_\-]+)$")
ALLOWED_CLOCK_SKEW = timedelta(minutes=5)


@dataclass
class EligibleObservation:
    observation_id: str
    event_id: str
    occurred_at: datetime
    sleep_hours: float
    productivity: float
    attributes: dict[str, Any]
    logical_source_id: str
    global_position: int
    recorded_at: datetime
    mapping_version: str | None = None


@dataclass
class EligibilityResult:
    eligible: list[EligibleObservation] = field(default_factory=list)
    excluded_count: int = 0
    exclusion_reasons: dict[str, int] = field(default_factory=dict)
    critical_data_quality_failure: bool = False

    def _exclude(self, reason: str) -> None:
        self.excluded_count += 1
        self.exclusion_reasons[reason] = self.exclusion_reasons.get(reason, 0) + 1


def extract_logical_source_id(source_ids: Any) -> str | None:
    if not source_ids:
        return None
    for sid in source_ids:
        text = str(sid)
        if SOURCE_ID_RE.match(text):
            return text
    return None


def _attrs(context: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(context, dict):
        return {}
    attributes = context.get("attributes")
    return attributes if isinstance(attributes, dict) else {}


def _conflict_payload(row: EligibleObservation) -> tuple[object, ...]:
    return (
        row.sleep_hours,
        row.productivity,
        row.occurred_at.isoformat() if row.occurred_at else None,
        row.mapping_version,
    )


def select_eligible_checkins(
    rows: list[Any],
    *,
    tenant_id: str,
    owner_id: str,
    application_id: str,
) -> EligibilityResult:
    """Filter projected observations into eligible daily check-ins.

    Deduplicates by logical source id (`lifemaxxxing://daily-check-ins/{id}`),
    keeping the lowest global_position. Conflicting payloads for the same
    source id mark critical_data_quality_failure.
    """
    result = EligibilityResult()
    by_source: dict[str, EligibleObservation] = {}

    # Sort for deterministic first-win: lowest global_position first.
    ordered = sorted(rows, key=lambda r: (int(getattr(r, "global_position", 0)), r.observation_id))

    for row in ordered:
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
        logical = extract_logical_source_id(getattr(row, "source_ids", ()))
        if logical is None:
            result._exclude("SOURCE_ID_FORMAT_REQUIRED")
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

        mapping_version = None
        if isinstance(meta.get("mapping_version"), str):
            mapping_version = meta["mapping_version"]
        elif isinstance(attrs.get("mapping_version"), str):
            mapping_version = attrs["mapping_version"]

        candidate = EligibleObservation(
            observation_id=row.observation_id,
            event_id=row.event_id,
            occurred_at=row.occurred_at,
            sleep_hours=sleep_f,
            productivity=prod_f,
            attributes=attrs,
            logical_source_id=logical,
            global_position=int(row.global_position),
            recorded_at=row.created_at,
            mapping_version=mapping_version,
        )

        existing = by_source.get(logical)
        if existing is None:
            by_source[logical] = candidate
            continue

        if _conflict_payload(existing) != _conflict_payload(candidate):
            result._exclude("DUPLICATE_SOURCE_CONFLICT")
            result.critical_data_quality_failure = True
            continue

        result._exclude("DUPLICATE_LOGICAL_SOURCE")
        # Keep lowest global_position (already ordered; existing wins).

    result.eligible = sorted(by_source.values(), key=lambda o: o.global_position)
    return result


def split_by_temporal_anchors(
    eligible: list[EligibleObservation],
    *,
    baseline_cutoff: datetime,
    prospective_start: datetime,
    activation_global_position: int,
    activation_recorded_at: datetime,
    evidence_cutoff_global_position: int,
    evidence_cutoff_recorded_at: datetime,
    evaluation_started_at: datetime,
) -> tuple[list[EligibleObservation], list[EligibleObservation], dict[str, int]]:
    """Partition into baseline / prospective with Stage 3.1 temporal proofs."""
    baseline: list[EligibleObservation] = []
    prospective: list[EligibleObservation] = []
    exclusions: dict[str, int] = {}

    def bump(reason: str) -> None:
        exclusions[reason] = exclusions.get(reason, 0) + 1

    future_limit = evaluation_started_at + ALLOWED_CLOCK_SKEW

    for o in eligible:
        # Future occurred_at relative to evaluation clock.
        if o.occurred_at > future_limit:
            bump("OCCURRED_AT_IN_FUTURE")
            continue

        # Baseline candidate by occurred_at.
        if o.occurred_at < baseline_cutoff:
            if (
                o.global_position < activation_global_position
                and o.recorded_at <= activation_recorded_at
            ):
                baseline.append(o)
            else:
                bump("BACKFILLED_AFTER_ACTIVATION")
            continue

        # Prospective candidate by occurred_at.
        if o.occurred_at >= prospective_start:
            if o.global_position <= activation_global_position:
                bump("PROSPECTIVE_REQUIRES_POST_ACTIVATION_GLOBAL_POSITION")
                continue
            if o.recorded_at < activation_recorded_at:
                bump("PROSPECTIVE_RECORDED_BEFORE_ACTIVATION")
                continue
            if o.global_position > evidence_cutoff_global_position:
                bump("OBSERVATION_RECORDED_AFTER_CUTOFF")
                continue
            if o.recorded_at > evidence_cutoff_recorded_at:
                bump("OBSERVATION_RECORDED_AFTER_CUTOFF")
                continue
            prospective.append(o)
            continue

        bump("BETWEEN_BASELINE_AND_PROSPECTIVE")

    return baseline, prospective, exclusions


def split_by_cutoff(
    eligible: list[EligibleObservation],
    *,
    baseline_cutoff: datetime,
    prospective_start: datetime,
) -> tuple[list[EligibleObservation], list[EligibleObservation]]:
    """Legacy helper retained for older unit tests; prefer split_by_temporal_anchors."""
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
