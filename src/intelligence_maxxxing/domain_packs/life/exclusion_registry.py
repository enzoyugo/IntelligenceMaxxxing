"""Append-only observation exclusion registry (no ledger DELETE/UPDATE).

Bootstrap + durable `observation_exclusions` table. Original observations remain
in engine_events / accepted_observations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

REASON_TEST_IN_PRODUCTION = "TEST_OBSERVATION_IN_PRODUCTION_LEDGER"

# Bootstrapped exclusions with evidence (sprint audit). Always merged with DB rows.
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
_db_cache: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class ExclusionRecord:
    target_observation_id: str
    reason_code: str
    reason: str
    invalidated_at: str
    actor_system: str
    evidence_report: str | None = None
    exclusion_id: str | None = None
    durable: bool = False


def _records_from_dicts(rows: list[dict[str, Any]], *, durable: bool) -> list[ExclusionRecord]:
    return [
        ExclusionRecord(
            target_observation_id=str(r["target_observation_id"]),
            reason_code=str(r["reason_code"]),
            reason=str(r["reason"]),
            invalidated_at=str(r["invalidated_at"]),
            actor_system=str(r["actor_system"]),
            evidence_report=r.get("evidence_report"),
            exclusion_id=r.get("exclusion_id"),
            durable=durable,
        )
        for r in rows
    ]


def refresh_db_exclusion_cache(session: Any | None = None) -> list[ExclusionRecord]:
    """Load durable exclusions into process cache. Safe if table missing."""
    global _db_cache
    rows: list[dict[str, Any]] = []
    try:
        if session is not None:
            from sqlalchemy import select

            from intelligence_maxxxing.infrastructure.database.tables import (
                ObservationExclusionRow,
            )

            for r in session.scalars(select(ObservationExclusionRow)).all():
                rows.append(
                    {
                        "exclusion_id": r.exclusion_id,
                        "target_observation_id": r.target_observation_id,
                        "reason_code": r.reason_code,
                        "reason": r.reason,
                        "invalidated_at": r.invalidated_at.isoformat()
                        if hasattr(r.invalidated_at, "isoformat")
                        else str(r.invalidated_at),
                        "actor_system": r.actor_system,
                        "evidence_report": r.evidence_report,
                    }
                )
        else:
            rows = _load_db_exclusions_via_settings()
    except Exception:  # noqa: BLE001 — selection must not fail if DB unavailable
        rows = []
    with _lock:
        _db_cache = rows
    return _records_from_dicts(rows, durable=True)


def _load_db_exclusions_via_settings() -> list[dict[str, Any]]:
    from sqlalchemy import create_engine, text

    from intelligence_maxxxing.config.settings import get_settings

    settings = get_settings()
    engine = create_engine(
        str(settings.database_url),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3},
    )
    sql = text(
        """
        SELECT exclusion_id, target_observation_id, reason_code, reason,
               invalidated_at, actor_system, evidence_report
        FROM observation_exclusions
        ORDER BY created_at
        """
    )
    out: list[dict[str, Any]] = []
    with engine.connect() as conn:
        for r in conn.execute(sql):
            out.append(
                {
                    "exclusion_id": r.exclusion_id,
                    "target_observation_id": r.target_observation_id,
                    "reason_code": r.reason_code,
                    "reason": r.reason,
                    "invalidated_at": r.invalidated_at.isoformat()
                    if hasattr(r.invalidated_at, "isoformat")
                    else str(r.invalidated_at),
                    "actor_system": r.actor_system,
                    "evidence_report": r.evidence_report,
                }
            )
    return out


def list_exclusions() -> list[ExclusionRecord]:
    with _lock:
        db_rows = list(_db_cache) if _db_cache is not None else None
        runtime = list(_runtime_exclusions)
    if db_rows is None:
        # Lazy load once; ignore failures (unit tests without DB).
        try:
            refresh_db_exclusion_cache()
            with _lock:
                db_rows = list(_db_cache or [])
        except Exception:  # noqa: BLE001
            db_rows = []
    merged: dict[str, ExclusionRecord] = {}
    for rec in _records_from_dicts(list(_BOOTSTRAP), durable=False):
        merged[rec.target_observation_id] = rec
    for rec in _records_from_dicts(db_rows, durable=True):
        merged[rec.target_observation_id] = rec
    for rec in _records_from_dicts(runtime, durable=False):
        merged.setdefault(rec.target_observation_id, rec)
    return list(merged.values())


def exclusion_id_set() -> frozenset[str]:
    return frozenset(r.target_observation_id for r in list_exclusions())


def append_exclusion(
    *,
    target_observation_id: str,
    reason_code: str = REASON_TEST_IN_PRODUCTION,
    reason: str,
    actor_system: str = "manual",
    evidence_report: str | None = None,
    session: Any | None = None,
) -> ExclusionRecord:
    """Append an exclusion. Never mutates prior records or observation bytes."""
    existing = next(
        (r for r in list_exclusions() if r.target_observation_id == target_observation_id),
        None,
    )
    if existing is not None:
        return existing

    now = datetime.now(UTC)
    record = {
        "exclusion_id": f"excl_{uuid4().hex[:24]}",
        "target_observation_id": target_observation_id,
        "reason_code": reason_code,
        "reason": reason,
        "invalidated_at": now.isoformat(),
        "actor_system": actor_system,
        "evidence_report": evidence_report,
    }
    if session is not None:
        from intelligence_maxxxing.infrastructure.database.tables import (
            ObservationExclusionRow,
        )

        session.add(
            ObservationExclusionRow(
                exclusion_id=record["exclusion_id"],
                target_observation_id=target_observation_id,
                reason_code=reason_code,
                reason=reason,
                invalidated_at=now,
                actor_system=actor_system,
                evidence_report=evidence_report,
                created_at=now,
            )
        )
        session.flush()
        refresh_db_exclusion_cache(session)
    else:
        with _lock:
            _runtime_exclusions.append(record)
    return ExclusionRecord(
        target_observation_id=target_observation_id,
        reason_code=reason_code,
        reason=reason,
        invalidated_at=record["invalidated_at"],
        actor_system=actor_system,
        evidence_report=evidence_report,
        exclusion_id=record["exclusion_id"],
        durable=session is not None,
    )


def ensure_bootstrap_durable(session: Any) -> ExclusionRecord | None:
    """Idempotently persist bootstrap exclusions into the DB table."""
    from intelligence_maxxxing.infrastructure.database.tables import (
        ObservationExclusionRow,
    )

    from sqlalchemy import select

    written: ExclusionRecord | None = None
    for boot in _BOOTSTRAP:
        oid = str(boot["target_observation_id"])
        exists = session.scalars(
            select(ObservationExclusionRow).where(
                ObservationExclusionRow.target_observation_id == oid
            )
        ).first()
        if exists:
            continue
        now = datetime.now(UTC)
        session.add(
            ObservationExclusionRow(
                exclusion_id=f"excl_boot_{oid[-24:]}",
                target_observation_id=oid,
                reason_code=str(boot["reason_code"]),
                reason=str(boot["reason"]),
                invalidated_at=datetime.fromisoformat(str(boot["invalidated_at"])),
                actor_system=str(boot["actor_system"]),
                evidence_report=boot.get("evidence_report"),
                created_at=now,
            )
        )
        written = ExclusionRecord(
            target_observation_id=oid,
            reason_code=str(boot["reason_code"]),
            reason=str(boot["reason"]),
            invalidated_at=str(boot["invalidated_at"]),
            actor_system=str(boot["actor_system"]),
            evidence_report=boot.get("evidence_report"),
            durable=True,
        )
    session.flush()
    refresh_db_exclusion_cache(session)
    return written
