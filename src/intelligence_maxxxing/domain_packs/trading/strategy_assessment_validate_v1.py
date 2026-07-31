"""Generic multi-strategy TMX↔IM assessment contract validation (IM-owned)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STRATEGY_REQUEST_SCHEMA_VERSION = "tmx.im.strategy.assessment.request.v1"
STRATEGY_ASSESSMENT_SCHEMA_VERSION = "im.tmx.strategy.assessment.v1"

STRATEGY_DECISIONS = frozenset({"TAKE", "REJECT", "ABSTAIN"})

STRATEGY_SCHEMA_FILES = (
    "tmx.im.strategy.assessment.request.v1.json",
    "im.tmx.strategy.assessment.v1.json",
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


def _require_object(payload: dict[str, Any], key: str, errors: list[str]) -> dict[str, Any] | None:
    value = payload.get(key)
    if value is None:
        errors.append(f"MISSING_FIELD:{key}")
        return None
    if not isinstance(value, dict):
        errors.append(f"NOT_OBJECT:{key}")
        return None
    return value


def extract_factor_states(trader_view: dict[str, Any]) -> list[dict[str, Any]]:
    states = trader_view.get("factor_states")
    if isinstance(states, list):
        return [row for row in states if isinstance(row, dict)]
    factors = trader_view.get("factors")
    if isinstance(factors, list):
        return [row for row in factors if isinstance(row, dict)]
    return []


def extract_available_at_map(request: dict[str, Any]) -> dict[str, str | None]:
    tv = request.get("trader_view") or {}
    out: dict[str, str | None] = {}
    for row in extract_factor_states(tv):
        if row.get("factor_id"):
            out[str(row["factor_id"])] = row.get("available_at")
    return out


def validate_strategy_request(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["NOT_OBJECT"]}
    if payload.get("schema_version") != STRATEGY_REQUEST_SCHEMA_VERSION:
        errors.append("SCHEMA_VERSION_MISMATCH")
    _require(
        payload,
        [
            "schema_version",
            "request_id",
            "run_id",
            "raw_setup_id",
            "idempotency_key",
            "strategy",
            "market",
            "setup",
            "trader_view",
            "costs",
            "lineage",
        ],
        errors,
    )
    leaks = forbidden_outcome_fields(payload)
    if leaks:
        errors.append(f"OUTCOME_LEAKAGE:{','.join(leaks[:8])}")

    strategy = _require_object(payload, "strategy", errors)
    if strategy is not None:
        _require(strategy, ["strategy_id", "strategy_version", "family", "profile_version"], errors)

    market = _require_object(payload, "market", errors)
    if market is not None:
        _require(market, ["market", "symbol", "timeframe", "signal_time", "available_at"], errors)

    setup = _require_object(payload, "setup", errors)
    if setup is not None:
        _require(setup, ["direction", "entry", "stop"], errors)

    trader_view = _require_object(payload, "trader_view", errors)
    if trader_view is not None:
        if "snapshot_version" not in trader_view:
            errors.append("MISSING_FIELD:trader_view.snapshot_version")
        states = extract_factor_states(trader_view)
        if not states and "factor_states" not in trader_view and "factors" not in trader_view:
            errors.append("MISSING_FIELD:trader_view.factor_states")

    costs = _require_object(payload, "costs", errors)
    if costs is not None:
        _require(costs, ["scenario_id"], errors)

    signal_dt = _parse_ts((market or {}).get("signal_time") if market else None)
    available_dt = _parse_ts((market or {}).get("available_at") if market else None)
    if signal_dt and available_dt and available_dt > signal_dt:
        errors.append("AVAILABLE_AT_AFTER_SIGNAL_TIME")

    if trader_view is not None:
        for row in extract_factor_states(trader_view):
            factor_avail = _parse_ts(row.get("available_at"))
            if factor_avail and signal_dt and factor_avail > signal_dt:
                errors.append(f"FUTURE_FACTOR_AVAILABLE_AT:{row.get('factor_id')}")

    causality = [
        e
        for e in errors
        if e.startswith(("AVAILABLE_AT_", "FUTURE_FACTOR_"))
    ]
    return {
        "ok": not errors,
        "errors": errors,
        "causality_errors": causality,
        "schema_version": STRATEGY_REQUEST_SCHEMA_VERSION,
    }


def validate_strategy_assessment(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["NOT_OBJECT"]}
    if payload.get("schema_version") != STRATEGY_ASSESSMENT_SCHEMA_VERSION:
        errors.append("SCHEMA_VERSION_MISMATCH")
    _require(
        payload,
        [
            "schema_version",
            "assessment_id",
            "request_id",
            "run_id",
            "raw_setup_id",
            "strategy",
            "decision",
            "reason_codes",
            "profile_version",
            "research_only",
            "factor_available_at_preserved",
            "input_hash",
            "output_hash",
            "created_at_utc",
        ],
        errors,
    )
    if payload.get("decision") not in STRATEGY_DECISIONS:
        errors.append("DECISION_INVALID")
    if payload.get("research_only") is not True:
        errors.append("RESEARCH_ONLY_REQUIRED")
    leaks = forbidden_outcome_fields(payload)
    if leaks:
        errors.append(f"OUTCOME_LEAKAGE:{','.join(leaks[:8])}")
    return {
        "ok": not errors,
        "errors": errors,
        "schema_version": STRATEGY_ASSESSMENT_SCHEMA_VERSION,
    }
