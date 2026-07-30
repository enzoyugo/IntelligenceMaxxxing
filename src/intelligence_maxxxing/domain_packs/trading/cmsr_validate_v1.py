"""CMSR TMX↔IM contract validation (IM-owned mirror of TMX bridge rules)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CMSR_REQUEST_SCHEMA_VERSION = "tmx.im.cmsr.assessment.request.v1"
CMSR_ASSESSMENT_SCHEMA_VERSION = "im.tmx.cmsr.assessment.v1"
CMSR_POLICY_ID = "IM_CMSR_DECISION_POLICY"
CMSR_POLICY_VERSION = "1.0.0"
CMSR_POLICY_FROZEN_AT_UTC = "2026-07-28T22:00:00Z"
CMSR_RULESET_HASH = "cmsr_decision_policy_v1_frozen_20260728"

CMSR_DECISIONS = frozenset({"TAKE", "REJECT", "ABSTAIN", "REDUCE_CONFIDENCE"})

CMSR_SCHEMA_FILES = (
    "tmx.im.cmsr.assessment.request.v1.json",
    "im.tmx.cmsr.assessment.v1.json",
)

FORBIDDEN_OUTCOME_FIELDS = frozenset(
    {
        "outcome",
        "exit_reason",
        "exit_time",
        "exit_time_utc",
        "realized_R",
        "gross_R",
        "trusted_net_R",
        "net_R",
        "mfe",
        "mae",
        "mfe_R",
        "mae_R",
        "resolved_at",
        "resolved_at_utc",
        "pnl",
        "pnl_R",
    }
)

_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "contracts" / "schemas" / "v1" / "trading"


def schema_dir() -> Path:
    return _SCHEMA_DIR


def schema_file_hash(name: str) -> str:
    return hashlib.sha256((schema_dir() / name).read_bytes()).hexdigest()


def canonical_json_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def content_hash(obj: Any) -> str:
    return hashlib.sha256(canonical_json_dumps(obj).encode("utf-8")).hexdigest()


def forbidden_outcome_fields(payload: dict[str, Any], *, path: str = "") -> list[str]:
    hits: list[str] = []
    for key, value in payload.items():
        here = f"{path}.{key}" if path else key
        if key in FORBIDDEN_OUTCOME_FIELDS:
            hits.append(here)
        if isinstance(value, dict):
            hits.extend(forbidden_outcome_fields(value, path=here))
    return hits


def _parse_ts(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _require(payload: dict[str, Any], fields: list[str], errors: list[str]) -> None:
    for field in fields:
        if field not in payload:
            errors.append(f"MISSING_FIELD:{field}")


def raw_setup_hash(raw_setup: dict[str, Any]) -> str:
    core = {
        "setup_id": raw_setup.get("setup_id"),
        "strategy_id": raw_setup.get("strategy_id"),
        "symbol": raw_setup.get("symbol"),
        "direction": raw_setup.get("direction"),
        "decision_time": raw_setup.get("decision_time"),
        "available_at": raw_setup.get("available_at"),
        "entry": raw_setup.get("entry"),
        "stop": raw_setup.get("stop"),
        "target": raw_setup.get("target"),
        "shock_id": raw_setup.get("shock_id"),
        "signal_id": raw_setup.get("signal_id"),
        "order_intent_id": raw_setup.get("order_intent_id"),
    }
    return content_hash(core)


def validate_cmsr_request(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["NOT_OBJECT"]}
    if payload.get("schema_version") != CMSR_REQUEST_SCHEMA_VERSION:
        errors.append("SCHEMA_VERSION_MISMATCH")
    _require(
        payload,
        [
            "schema_version",
            "request_id",
            "experiment_id",
            "setup_id",
            "raw_setup_hash",
            "strategy_id",
            "decision_time",
            "available_at_utc",
            "idempotency_key",
            "trader_view_snapshot",
            "raw_setup",
            "provenance",
        ],
        errors,
    )
    leaks = forbidden_outcome_fields(payload)
    if leaks:
        errors.append(f"OUTCOME_LEAKAGE:{','.join(leaks[:8])}")

    raw = payload.get("raw_setup") or {}
    if isinstance(raw, dict):
        expected = raw_setup_hash(raw)
        if payload.get("raw_setup_hash") != expected:
            errors.append("RAW_SETUP_HASH_MISMATCH")
        if raw.get("setup_id") != payload.get("setup_id"):
            errors.append("SETUP_ID_MISMATCH")

    decision_dt = _parse_ts(payload.get("decision_time"))
    available_dt = _parse_ts(payload.get("available_at_utc"))
    if decision_dt and available_dt and available_dt > decision_dt:
        errors.append("AVAILABLE_AT_AFTER_DECISION_TIME")

    snap = payload.get("trader_view_snapshot") or {}
    if isinstance(snap, dict):
        snap_dt = _parse_ts(snap.get("decision_time"))
        if snap_dt and decision_dt and snap_dt != decision_dt:
            errors.append("SNAPSHOT_DECISION_TIME_MISMATCH")
        for row in snap.get("factors") or []:
            if not isinstance(row, dict):
                errors.append("FACTOR_MALFORMED")
                continue
            factor_avail = _parse_ts(row.get("available_at"))
            if factor_avail and decision_dt and factor_avail > decision_dt:
                errors.append(f"FUTURE_FACTOR_AVAILABLE_AT:{row.get('factor_id')}")

    causality = [e for e in errors if e.startswith(("AVAILABLE_AT_", "FUTURE_FACTOR_", "SNAPSHOT_DECISION_"))]
    return {
        "ok": not errors,
        "errors": errors,
        "causality_errors": causality,
        "schema_version": CMSR_REQUEST_SCHEMA_VERSION,
    }


def validate_cmsr_assessment(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["NOT_OBJECT"]}
    if payload.get("schema_version") != CMSR_ASSESSMENT_SCHEMA_VERSION:
        errors.append("SCHEMA_VERSION_MISMATCH")
    _require(
        payload,
        [
            "schema_version",
            "assessment_id",
            "request_id",
            "experiment_id",
            "setup_id",
            "raw_setup_hash",
            "policy_id",
            "policy_version",
            "policy_frozen_at_utc",
            "ruleset_hash",
            "decision",
            "reason_codes",
            "factor_available_at_preserved",
            "input_hash",
            "output_hash",
            "created_at_utc",
        ],
        errors,
    )
    if payload.get("decision") not in CMSR_DECISIONS:
        errors.append("DECISION_INVALID")
    if payload.get("policy_id") != CMSR_POLICY_ID:
        errors.append("POLICY_ID_MISMATCH")
    leaks = forbidden_outcome_fields(payload)
    if leaks:
        errors.append(f"OUTCOME_LEAKAGE:{','.join(leaks[:8])}")
    return {"ok": not errors, "errors": errors, "schema_version": CMSR_ASSESSMENT_SCHEMA_VERSION}


def extract_available_at_map(request: dict[str, Any]) -> dict[str, str | None]:
    snap = request.get("trader_view_snapshot") or {}
    out: dict[str, str | None] = {}
    for row in snap.get("factors") or []:
        if isinstance(row, dict) and row.get("factor_id"):
            out[str(row["factor_id"])] = row.get("available_at")
    return out
