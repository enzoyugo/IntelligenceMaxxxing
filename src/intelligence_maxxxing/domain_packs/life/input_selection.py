"""Canonical wellbeing observation selection — shared by V1 and V2.

Policy version: wellbeing_input_selection_v1

Production personal scores consume only USER_OBSERVATION evidence under an
explicit policy. Test/smoke/fixture observations are excluded structurally —
never by magnitude heuristics or bare ID substring matching alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from intelligence_maxxxing.domain_packs.life.observation_provenance import (
    NON_PRODUCTIVE_PURPOSES,
    ObservationEnvironment,
    ObservationPurpose,
    SubjectScope,
    extract_provenance,
)

INPUT_SELECTION_POLICY_VERSION = "wellbeing_input_selection_v1"

# Explicit registry of known production-ledger test artefacts (evidence-backed).
# Not a heuristic: each entry is documented in sprint reports / smoke scripts.
KNOWN_TEST_SOURCE_PREFIXES: tuple[str, ...] = (
    "lifemaxxxing://daily-check-ins/smoke-E2E_SCALE_CONTRACT_V1",
    "lifemaxxxing://daily-check-ins/smoke-E2E_WELLBEING_ACTIVATION",
    # Synthetic activation cohort (0–100 magnitudes without scale tags).
    "lifemaxxxing://daily-check-ins/local-E2E_WELLBEING_ACTIVATION",
)

KNOWN_TEST_OBSERVATION_IDS: frozenset[str] = frozenset(
    {
        # SCALE_CONTRACT smoke retained in personal ledger (audit target).
        "obs_ab746ef9d6c64732990a6e7fc4aaea15",
    }
)


class SelectionDecision(StrEnum):
    INCLUDED = "INCLUDED"
    EXCLUDED_TEST = "EXCLUDED_TEST"
    EXCLUDED_INVALIDATED = "EXCLUDED_INVALIDATED"
    EXCLUDED_WRONG_SUBJECT = "EXCLUDED_WRONG_SUBJECT"
    EXCLUDED_WRONG_ENVIRONMENT = "EXCLUDED_WRONG_ENVIRONMENT"
    EXCLUDED_UNSUPPORTED_CONTRACT = "EXCLUDED_UNSUPPORTED_CONTRACT"
    EXCLUDED_AMBIGUOUS = "EXCLUDED_AMBIGUOUS"


@dataclass
class SelectionReport:
    included: list[Any] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def included_observation_count(self) -> int:
        return len(self.included)

    @property
    def excluded_test_count(self) -> int:
        return sum(1 for d in self.decisions if d["decision"] == SelectionDecision.EXCLUDED_TEST)

    @property
    def excluded_invalidated_count(self) -> int:
        return sum(
            1 for d in self.decisions if d["decision"] == SelectionDecision.EXCLUDED_INVALIDATED
        )

    @property
    def excluded_ambiguous_count(self) -> int:
        return sum(
            1 for d in self.decisions if d["decision"] == SelectionDecision.EXCLUDED_AMBIGUOUS
        )

    def as_features(self) -> dict[str, Any]:
        return {
            "input_selection_policy_version": INPUT_SELECTION_POLICY_VERSION,
            "included_observation_count": self.included_observation_count,
            "excluded_test_count": self.excluded_test_count,
            "excluded_invalidated_count": self.excluded_invalidated_count,
            "excluded_ambiguous_count": self.excluded_ambiguous_count,
            "subject_scope": SubjectScope.PERSONAL.value,
            "environment": ObservationEnvironment.PRODUCTION.value,
        }


def _matches_known_test_source(source_ids: list[str]) -> bool:
    for sid in source_ids:
        text = str(sid)
        for prefix in KNOWN_TEST_SOURCE_PREFIXES:
            if text.startswith(prefix):
                return True
    return False


def classify_for_personal_production(
    row: Any,
    *,
    exclusion_ids: frozenset[str] | set[str] | None = None,
) -> SelectionDecision:
    """Decide whether a row may feed personal PRODUCTION wellbeing scores."""
    exclusion_ids = exclusion_ids or frozenset()
    prov = extract_provenance(row)
    oid = prov.get("observation_id")
    meta = prov.get("metadata") or {}
    subject = getattr(row, "subject", None)
    life_event = meta.get("life_event_type")

    if oid and str(oid) in exclusion_ids:
        return SelectionDecision.EXCLUDED_INVALIDATED

    if oid and str(oid) in KNOWN_TEST_OBSERVATION_IDS:
        return SelectionDecision.EXCLUDED_TEST

    if _matches_known_test_source(list(prov.get("source_ids") or [])):
        return SelectionDecision.EXCLUDED_TEST

    purpose = prov.get("purpose")
    environment = prov.get("environment")
    subject_scope = prov.get("subject_scope")

    if purpose in NON_PRODUCTIVE_PURPOSES:
        return SelectionDecision.EXCLUDED_TEST

    if subject_scope is SubjectScope.TEST_PROFILE:
        return SelectionDecision.EXCLUDED_WRONG_SUBJECT

    if environment is ObservationEnvironment.TEST:
        return SelectionDecision.EXCLUDED_WRONG_ENVIRONMENT

    if environment is ObservationEnvironment.DEVELOPMENT and purpose is not ObservationPurpose.USER_OBSERVATION:
        return SelectionDecision.EXCLUDED_WRONG_ENVIRONMENT

    # Workouts: legacy rows without provenance remain eligible unless tagged test.
    if subject == "workout" or life_event == "life.workout.completed.v1":
        if purpose is ObservationPurpose.USER_OBSERVATION or purpose is None:
            return SelectionDecision.INCLUDED
        return SelectionDecision.EXCLUDED_TEST

    # Explicit production user observation
    if purpose is ObservationPurpose.USER_OBSERVATION:
        if environment in (None, ObservationEnvironment.PRODUCTION, ObservationEnvironment.DEVELOPMENT):
            if subject_scope in (None, SubjectScope.PERSONAL):
                return SelectionDecision.INCLUDED
        return SelectionDecision.EXCLUDED_WRONG_ENVIRONMENT

    # Legacy LifeOS Daily Flow (pre-provenance): personal URI without smoke prefixes.
    source_ids = [str(s) for s in (prov.get("source_ids") or [])]
    if any(s.startswith("lifemaxxxing://daily-check-ins/") for s in source_ids):
        if purpose is None and environment in (None, ObservationEnvironment.PRODUCTION):
            return SelectionDecision.INCLUDED

    # Untagged synthetic / bare attributes without known source → ambiguous (exclude).
    if purpose is None and environment is None and not source_ids:
        return SelectionDecision.EXCLUDED_AMBIGUOUS

    if purpose is None and environment is None:
        return SelectionDecision.EXCLUDED_AMBIGUOUS

    if purpose is ObservationPurpose.MIGRATION or purpose is ObservationPurpose.BACKFILL:
        return SelectionDecision.EXCLUDED_UNSUPPORTED_CONTRACT

    return SelectionDecision.EXCLUDED_AMBIGUOUS


def select_effective_observations(
    rows: list[Any],
    *,
    exclusion_ids: frozenset[str] | set[str] | None = None,
) -> tuple[list[Any], SelectionReport]:
    """Filter rows for personal production wellbeing; V1/V2 must share this set."""
    report = SelectionReport()
    for row in rows:
        decision = classify_for_personal_production(row, exclusion_ids=exclusion_ids)
        oid = getattr(row, "observation_id", None)
        report.decisions.append(
            {
                "observation_id": oid,
                "decision": decision,
                "global_position": getattr(row, "global_position", None),
            }
        )
        if decision is SelectionDecision.INCLUDED:
            report.included.append(row)
    return report.included, report
