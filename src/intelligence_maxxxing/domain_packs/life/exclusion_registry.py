"""Append-only observation exclusion registry (no ledger DELETE/UPDATE).

Exclusions are additive records. Original observations remain in engine_events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Any

REASON_TEST_IN_PRODUCTION = "TEST_OBSERVATION_IN_PRODUCTION_LEDGER"

# Bootstrapped exclusions with evidence (sprint audit). Append-only process memory
# plus optional DB table; never removes entries.
_BOOTSTRAP: tuple[dict[str, Any], ...] = (
    {
        "target_observation_id": "obs_ab746ef9d6c64732990a6e7fc4aaea15",
        "reason_code": REASON_TEST_IN_PRODUCTION,
        "reason": (
            "SCALE_CONTRACT_V1 smoke observation retained in personal ledger; "
            "source_ids prefix smoke-E2E_SCALE_CONTRACT_V1; excluded from "
            "personal wellbeing input selection."
        ),
        "invalidated_at": "2026-07-21T00:00:00+00:00",
        "actor_system": "wellbeing_test_isolation_v1",
        "evidence_report": "WELLBEING_EXISTING_SMOKE_CONTAMINATION_AUDIT_V1",
    },
)

_lock = Lock()
_runtime_exclusions: list[dict[str, Any]] = []


@dataclass(frozen=True)
class ExclusionRecord:
    target_observation_id: str
    reason_code: str
    reason: str
    invalidated_at: str
    actor_system: str
    evidence_report: str | None = None


def list_exclusions() -> list[ExclusionRecord]:
    with _lock:
        rows = list(_BOOTSTRAP) + list(_runtime_exclusions)
    return [
        ExclusionRecord(
            target_observation_id=str(r["target_observation_id"]),
            reason_code=str(r["reason_code"]),
            reason=str(r["reason"]),
            invalidated_at=str(r["invalidated_at"]),
            actor_system=str(r["actor_system"]),
            evidence_report=r.get("evidence_report"),
        )
        for r in rows
    ]


def exclusion_id_set() -> frozenset[str]:
    return frozenset(r.target_observation_id for r in list_exclusions())


def append_exclusion(
    *,
    target_observation_id: str,
    reason_code: str = REASON_TEST_IN_PRODUCTION,
    reason: str,
    actor_system: str = "manual",
    evidence_report: str | None = None,
) -> ExclusionRecord:
    """Append an exclusion. Never mutates prior records or observation bytes."""
    record = {
        "target_observation_id": target_observation_id,
        "reason_code": reason_code,
        "reason": reason,
        "invalidated_at": datetime.now(UTC).isoformat(),
        "actor_system": actor_system,
        "evidence_report": evidence_report,
    }
    with _lock:
        if any(
            r.get("target_observation_id") == target_observation_id
            for r in list(_BOOTSTRAP) + _runtime_exclusions
        ):
            # Idempotent append: keep first record; do not duplicate.
            return next(
                r
                for r in list_exclusions()
                if r.target_observation_id == target_observation_id
            )
        _runtime_exclusions.append(record)
    return ExclusionRecord(
        target_observation_id=target_observation_id,
        reason_code=reason_code,
        reason=reason,
        invalidated_at=record["invalidated_at"],
        actor_system=actor_system,
        evidence_report=evidence_report,
    )
