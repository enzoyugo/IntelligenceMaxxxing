"""Live closeout: DB identity, contamination audit, with/without recompute.

Does not print secrets. Writes JSON under artifacts/isolation_closeout/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy import create_engine, text

from intelligence_maxxxing.config.settings import get_settings
from intelligence_maxxxing.domain_packs.life.exclusion_registry import (
    REASON_TEST_IN_PRODUCTION,
    exclusion_id_set,
    list_exclusions,
    refresh_db_exclusion_cache,
)
from intelligence_maxxxing.domain_packs.life.input_selection import (
    INPUT_SELECTION_POLICY_VERSION,
    select_effective_observations,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v1 import (
    compute_wellbeing_v1,
    extract_checkin_days,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.pipeline import compute_wellbeing_v2

SMOKE_ID = "obs_ab746ef9d6c64732990a6e7fc4aaea15"


def _db_fingerprint(url: str) -> dict[str, str]:
    # postgresql+psycopg://user:pass@host:port/dbname
    safe = url
    if "@" in safe:
        safe = safe.split("@", 1)[1]
    host_port_db = safe
    name = host_port_db.rsplit("/", 1)[-1] if "/" in host_port_db else "unknown"
    host = host_port_db.split("/")[0] if "/" in host_port_db else host_port_db
    digest = hashlib.sha256(host_port_db.encode()).hexdigest()[:16]
    return {
        "database_name": name,
        "host_port": host,
        "identity_fingerprint": digest,
        "is_temp_iso_smoke": "iso_smoke" in name,
        "is_personal_default": name == "intelligence_maxxxing",
    }


def _connect():
    settings = get_settings()
    url = str(settings.database_url)
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5}), url


def ledger_stats(conn) -> dict[str, Any]:
    rows = conn.execute(text("SELECT COUNT(*) AS c FROM accepted_observations")).scalar()
    pos = conn.execute(
        text("SELECT COALESCE(MAX(global_position),0) FROM accepted_observations")
    ).scalar()
    return {"accepted_observation_count": int(rows or 0), "latest_global_position": int(pos or 0)}


def load_checkin_rows(conn) -> list[Any]:
    sql = text(
        """
        SELECT observation_id, global_position, occurred_at, domain_pack, subject,
               source_ids, meta, context
        FROM accepted_observations
        WHERE domain_pack = 'life' AND subject = 'daily_check_in'
        ORDER BY global_position
        """
    )
    out: list[Any] = []
    for r in conn.execute(sql):
        out.append(
            SimpleNamespace(
                observation_id=r.observation_id,
                global_position=r.global_position,
                occurred_at=r.occurred_at,
                domain_pack=r.domain_pack,
                subject=r.subject,
                source_ids=list(r.source_ids or []),
                metadata=dict(r.meta or {}),
                context=dict(r.context or {}),
            )
        )
    return out


def audit_smoke(conn) -> dict[str, Any]:
    row = conn.execute(
        text(
            """
            SELECT observation_id, global_position, occurred_at, source_ids, meta, context
            FROM accepted_observations WHERE observation_id = :oid
            """
        ),
        {"oid": SMOKE_ID},
    ).mappings().first()
    excl = conn.execute(
        text(
            """
            SELECT exclusion_id, target_observation_id, reason_code, reason,
                   invalidated_at, actor_system, evidence_report
            FROM observation_exclusions WHERE target_observation_id = :oid
            """
        ),
        {"oid": SMOKE_ID},
    ).mappings().first()
    refresh_db_exclusion_cache()
    effective_ids = exclusion_id_set()
    return {
        "original_observation": dict(row) if row else None,
        "original_present": row is not None,
        "correction_record": dict(excl) if excl else None,
        "correction_present": excl is not None,
        "effective_excluded": SMOKE_ID in effective_ids,
        "reason_code": (excl or {}).get("reason_code") if excl else None,
        "exclusions_in_process": [r.target_observation_id for r in list_exclusions()],
    }


def compare_with_without(rows: list[Any]) -> dict[str, Any]:
    # A: old policy = no exclusion / include known smoke if present
    with_smoke = list(rows)
    # B: current policy
    days_b = extract_checkin_days(rows)
    r_b = compute_wellbeing_v1(days_b, window_days=14) if days_b else None
    v2_b = compute_wellbeing_v2(rows, window_days=14)

    # Force include smoke for "with" by temporarily computing without exclusion filter:
    # re-extract using only INCLUDED + the smoke row if present.
    included, report = select_effective_observations(rows, exclusion_ids=frozenset())
    # Old policy approximation: all check-ins that are not EXCLUDED_AMBIGUOUS bare
    # Use raw rows filtered only by event type via extract with empty exclusions
    # but also inject smoke even if tagged — use select without exclusion_ids and
    # without known-test by cloning smoke purpose away... Simpler path:
    # compute from days built from all life.daily_check_in rows ignoring selection.
    from intelligence_maxxxing.domain_packs.life import wellbeing_v1 as v1mod

    by_day = {}
    ordered = sorted(with_smoke, key=lambda r: (int(r.global_position or 0), r.observation_id or ""))
    # Bypass selection: call inner loop by temporarily selecting all with USER purpose
    patched = []
    for r in ordered:
        meta = dict(r.metadata or {})
        meta.setdefault("life_event_type", "life.daily_check_in.completed.v1")
        meta["observation_purpose"] = "USER_OBSERVATION"
        ctx = dict(r.context or {})
        ctx["environment"] = "PRODUCTION"
        patched.append(
            SimpleNamespace(
                **{
                    **r.__dict__,
                    "metadata": meta,
                    "context": ctx,
                    "source_ids": [
                        s
                        for s in (r.source_ids or [])
                        if "smoke-E2E" not in str(s)
                    ]
                    or [f"lifemaxxxing://daily-check-ins/legacy-{r.observation_id}"],
                }
            )
        )
    # For true "with smoke" include smoke as productive by rewriting its source
    with_rows = []
    for r in ordered:
        meta = dict(r.metadata or {})
        meta["life_event_type"] = "life.daily_check_in.completed.v1"
        meta["observation_purpose"] = "USER_OBSERVATION"
        ctx = dict(r.context or {})
        ctx["environment"] = "PRODUCTION"
        # Keep original source_ids so smoke is included when exclusions empty AND
        # we bypass known-test by using a copy without known id for non-smoke;
        # for smoke keep id but empty known-test path via exclusion_ids empty and
        # rename observation_id temporarily for selection then restore values.
        oid = r.observation_id
        fake_oid = oid
        source_ids = list(r.source_ids or [])
        if oid == SMOKE_ID:
            fake_oid = "obs_force_include_smoke_for_compare"
            source_ids = [f"lifemaxxxing://daily-check-ins/force-include-{fake_oid}"]
        with_rows.append(
            SimpleNamespace(
                observation_id=fake_oid,
                global_position=r.global_position,
                occurred_at=r.occurred_at,
                domain_pack=r.domain_pack,
                subject=r.subject,
                source_ids=source_ids,
                metadata=meta,
                context=ctx,
            )
        )
    days_a = extract_checkin_days(with_rows)
    r_a = compute_wellbeing_v1(days_a, window_days=14) if days_a else None

    def pack(result: Any) -> dict[str, Any] | None:
        if result is None:
            return None
        return {
            "happiness": result.happiness,
            "stress": result.stress,
            "confidence": result.confidence,
            "sample_size": result.sample_size,
            "data_sufficiency": str(result.data_sufficiency),
            "early_warning": str(result.early_warning),
            "contributors": result.contributors,
            "features": {
                k: result.features.get(k)
                for k in (
                    "avg_happiness_normalized",
                    "avg_stress_normalized",
                    "missing_domains",
                )
                if isinstance(result.features, dict)
            },
        }

    # Selection report under current policy
    _, sel = select_effective_observations(rows, exclusion_ids=exclusion_id_set())
    return {
        "with_smoke_v1": pack(r_a),
        "without_smoke_v1": pack(r_b),
        "without_smoke_v2": {
            "happiness": v2_b.happiness_score,
            "stress": v2_b.stress_score,
            "confidence": v2_b.confidence_score,
            "sample_size": v2_b.sample_size,
            "formula_status": v2_b.formula_status,
            "change_state": v2_b.change_state,
            "input_fingerprint": v2_b.input_fingerprint,
        },
        "selection": sel.as_features(),
        "input_selection_policy_version": INPUT_SELECTION_POLICY_VERSION,
        "deltas": {
            "happiness": None
            if not r_a or not r_b
            else round(float(r_b.happiness or 0) - float(r_a.happiness or 0), 4),
            "stress": None
            if not r_a or not r_b
            else round(float(r_b.stress or 0) - float(r_a.stress or 0), 4),
            "confidence": None
            if not r_a or not r_b
            else round(float(r_b.confidence or 0) - float(r_a.confidence or 0), 4),
            "sample_size": None
            if not r_a or not r_b
            else int(r_b.sample_size) - int(r_a.sample_size),
        },
        "included_count": sel.included_observation_count,
        "excluded_test": sel.excluded_test_count,
        "excluded_invalidated": sel.excluded_invalidated_count,
        "excluded_ambiguous": sel.excluded_ambiguous_count,
    }


def migration_revision(conn) -> str | None:
    try:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/isolation_closeout/live_closeout.json")
    args = parser.parse_args()

    engine, url = _connect()
    fp = _db_fingerprint(url)
    if fp["is_temp_iso_smoke"]:
        print("REFUSING: DATABASE_URL points at temporary iso_smoke database", file=sys.stderr)
        return 2

    out: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "database": fp,
    }
    with engine.connect() as conn:
        out["migration_revision"] = migration_revision(conn)
        out["ledger"] = ledger_stats(conn)
        # Ensure exclusion table exists (migration must be applied separately)
        try:
            out["smoke_audit"] = audit_smoke(conn)
        except Exception as exc:  # noqa: BLE001
            out["smoke_audit_error"] = str(exc)
            out["smoke_audit"] = None
        rows = load_checkin_rows(conn)
        out["checkin_row_count"] = len(rows)
        out["comparison"] = compare_with_without(rows)
        snaps = conn.execute(
            text(
                """
                SELECT score_snapshot_id, formula_id, formula_version, happiness, stress,
                       confidence, computed_at, as_of_global_position,
                       input_fingerprint, data_sufficiency, early_warning
                FROM wellbeing_score_snapshots
                ORDER BY computed_at DESC LIMIT 20
                """
            )
        ).mappings().all()
        out["recent_snapshots"] = [dict(s) for s in snaps]

    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"wrote": str(path), "database": fp, "ledger": out.get("ledger")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
