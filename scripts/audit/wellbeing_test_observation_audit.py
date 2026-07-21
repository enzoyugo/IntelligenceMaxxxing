"""Classify wellbeing-related observations for test-isolation audit.

Read-only by default. --emit-invalidation-plan writes a plan JSON only.
Does not mutate the ledger.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from intelligence_maxxxing.domain_packs.life.exclusion_registry import exclusion_id_set
from intelligence_maxxxing.domain_packs.life.input_selection import (
    SelectionDecision,
    classify_for_personal_production,
)
from intelligence_maxxxing.domain_packs.life.observation_provenance import extract_provenance


@dataclass
class AuditRow:
    observation_id: str
    global_position: int | None
    date: str | None
    classification: str
    evidence: str
    included_in_current_scores: bool
    affected_snapshots: list[str]
    recommended_action: str


def _classify_label(decision: SelectionDecision, purpose: Any) -> str:
    if decision is SelectionDecision.EXCLUDED_INVALIDATED:
        return "INVALIDATED"
    if decision is SelectionDecision.EXCLUDED_TEST:
        if purpose and str(purpose) == "DEMO":
            return "DEMO"
        if purpose and str(purpose) == "FIXTURE":
            return "KNOWN_FIXTURE"
        if purpose and str(purpose) in ("MIGRATION", "BACKFILL"):
            return "MIGRATION"
        return "KNOWN_TEST"
    if decision is SelectionDecision.INCLUDED:
        return "PERSONAL_PRODUCTION"
    if decision is SelectionDecision.EXCLUDED_AMBIGUOUS:
        return "AMBIGUOUS"
    return decision.value


def audit_rows(rows: list[Any]) -> list[AuditRow]:
    exclusions = exclusion_id_set()
    out: list[AuditRow] = []
    for row in rows:
        decision = classify_for_personal_production(row, exclusion_ids=exclusions)
        prov = extract_provenance(row)
        purpose = prov.get("purpose")
        label = _classify_label(decision, purpose)
        oid = str(getattr(row, "observation_id", "") or "")
        occurred = getattr(row, "occurred_at", None)
        day = None
        if occurred is not None and hasattr(occurred, "date"):
            day = occurred.date().isoformat()
        evidence_parts = [
            f"decision={decision.value}",
            f"purpose={purpose}",
            f"environment={prov.get('environment')}",
            f"subject_scope={prov.get('subject_scope')}",
            f"source_ids={list(prov.get('source_ids') or [])}",
        ]
        included = decision is SelectionDecision.INCLUDED
        action = "NONE"
        if label in ("KNOWN_TEST", "KNOWN_FIXTURE", "DEMO") and oid not in exclusions:
            action = "APPEND_EXCLUSION"
        elif label == "AMBIGUOUS":
            action = "REVIEW_LEGACY_POLICY"
        elif label == "INVALIDATED":
            action = "ALREADY_EXCLUDED"
        out.append(
            AuditRow(
                observation_id=oid,
                global_position=getattr(row, "global_position", None),
                date=day,
                classification=label,
                evidence="; ".join(str(p) for p in evidence_parts),
                included_in_current_scores=included,
                affected_snapshots=[],
                recommended_action=action,
            )
        )
    return out


def emit_invalidation_plan(rows: list[AuditRow]) -> dict[str, Any]:
    targets = [r for r in rows if r.recommended_action == "APPEND_EXCLUSION"]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "plan_only",
        "note": "Apply via a separate auditable command; this file does not mutate.",
        "reason_code": "TEST_OBSERVATION_IN_PRODUCTION_LEDGER",
        "targets": [
            {
                "target_observation_id": r.observation_id,
                "evidence": r.evidence,
                "classification": r.classification,
            }
            for r in targets
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-json",
        help="Path to JSON list of observation-like dicts (offline). "
        "If omitted, attempts live DB projection (requires DATABASE_URL).",
    )
    parser.add_argument("--emit-invalidation-plan", action="store_true")
    parser.add_argument("--out", default="-")
    args = parser.parse_args(argv)

    rows: list[Any] = []
    if args.from_json:
        payload = json.loads(Path_read(args.from_json))
        from types import SimpleNamespace

        for item in payload:
            rows.append(SimpleNamespace(**item))
    else:
        try:
            rows = _load_from_db()
        except Exception as exc:  # noqa: BLE001 — audit must degrade gracefully
            print(f"LIVE_DB_UNAVAILABLE: {exc}", file=sys.stderr)
            # Seed known smoke target for offline classification proof.
            from types import SimpleNamespace

            rows = [
                SimpleNamespace(
                    observation_id="obs_ab746ef9d6c64732990a6e7fc4aaea15",
                    global_position=None,
                    occurred_at=None,
                    domain_pack="life",
                    subject="daily_check_in",
                    source_ids=[
                        "lifemaxxxing://daily-check-ins/smoke-E2E_SCALE_CONTRACT_V1"
                    ],
                    metadata={
                        "life_event_type": "life.daily_check_in.completed.v1",
                    },
                    context={
                        "attributes": {
                            "happiness": 5,
                            "stress": 10,
                            "happiness_scale": "0_100",
                            "stress_scale": "0_100",
                        }
                    },
                )
            ]

    audited = audit_rows(rows)
    output: dict[str, Any] = {
        "policy": "wellbeing_input_selection_v1",
        "count": len(audited),
        "rows": [asdict(r) for r in audited],
    }
    if args.emit_invalidation_plan:
        output["invalidation_plan"] = emit_invalidation_plan(audited)

    text = json.dumps(output, indent=2, default=str)
    if args.out == "-":
        print(text)
    else:
        Path_write(args.out, text)
    return 0


def Path_read(path: str) -> str:
    from pathlib import Path

    return Path(path).read_text(encoding="utf-8")


def Path_write(path: str, text: str) -> None:
    from pathlib import Path

    Path(path).write_text(text, encoding="utf-8")


def _load_from_db() -> list[Any]:
    """Best-effort load of life daily_check_in rows from the configured Engine DB."""
    from types import SimpleNamespace

    from sqlalchemy import create_engine, text

    from intelligence_maxxxing.config.settings import get_settings

    settings = get_settings()
    # Fail fast when Docker/Postgres is down (avoid multi-minute TCP hang).
    engine = create_engine(
        str(settings.database_url),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3},
    )
    sql = text(
        """
        SELECT observation_id, global_position, occurred_at, domain_pack, subject,
               source_ids, meta, context
        FROM accepted_observations
        WHERE domain_pack = 'life' AND subject = 'daily_check_in'
        ORDER BY global_position
        """
    )
    rows: list[Any] = []
    with engine.connect() as conn:
        for r in conn.execute(sql):
            rows.append(
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
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
