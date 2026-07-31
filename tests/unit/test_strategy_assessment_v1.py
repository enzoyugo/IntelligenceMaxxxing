"""Unit tests for generic strategy assessment validation and profiles."""

from __future__ import annotations

from copy import deepcopy

import pytest

from intelligence_maxxxing.domain_packs.trading.strategy_assessment_validate_v1 import (
    FORBIDDEN_OUTCOME_FIELDS,
    STRATEGY_ASSESSMENT_SCHEMA_VERSION,
    STRATEGY_REQUEST_SCHEMA_VERSION,
    forbidden_outcome_fields,
    validate_strategy_assessment,
    validate_strategy_request,
)
from intelligence_maxxxing.domain_packs.trading.strategy_profiles_v1 import (
    PROFILE_REGISTRY,
    assess_strategy_request,
)


def _base_request(*, strategy_id: str = "LONDON_NY_BREAKOUT") -> dict:
    signal_time = "2026-07-21T12:00:00Z"
    factor_states = [
        {
            "factor_id": "session_context",
            "status": "AVAILABLE_HIGH",
            "value": "LONDON",
            "confidence": 0.9,
            "available_at": signal_time,
            "strategy_criticality": "REQUIRED",
        },
        {
            "factor_id": "geometry_valid",
            "status": "AVAILABLE_HIGH",
            "value": True,
            "confidence": 0.95,
            "available_at": signal_time,
            "strategy_criticality": "REQUIRED",
        },
        {
            "factor_id": "cost_burden",
            "status": "AVAILABLE_HIGH",
            "value": 0.05,
            "confidence": 0.88,
            "available_at": signal_time,
            "strategy_criticality": "REQUIRED",
        },
    ]
    return {
        "schema_version": STRATEGY_REQUEST_SCHEMA_VERSION,
        "request_id": "req_strat_unit_001",
        "run_id": "run_strat_unit_001",
        "raw_setup_id": "setup_strat_unit_001",
        "idempotency_key": "STRAT_IDEM_unit_001",
        "strategy": {
            "strategy_id": strategy_id,
            "strategy_version": "1.0.0",
            "family": strategy_id,
            "profile_version": "1.0.0",
        },
        "market": {
            "market": "FX",
            "symbol": "EURUSD",
            "timeframe": "M5",
            "signal_time": signal_time,
            "available_at": signal_time,
        },
        "setup": {
            "direction": "LONG",
            "entry": 1.0910,
            "stop": 1.0890,
            "target": 1.0950,
        },
        "trader_view": {
            "snapshot_version": "trader_view_snapshot.v3",
            "factor_states": factor_states,
        },
        "costs": {
            "scenario_id": "C0_LOT_BASED_COMMISSION_RECONSTRUCTED",
            "commission_r": 0.05,
        },
        "lineage": {"tmx_commit": "abc123", "im_commit": "def456"},
    }


def test_validate_strategy_request_ok() -> None:
    result = validate_strategy_request(_base_request())
    assert result["ok"] is True
    assert result["errors"] == []


def test_validate_strategy_request_rejects_outcome_leakage() -> None:
    bad = _base_request()
    bad["pnl"] = 1.0
    result = validate_strategy_request(bad)
    assert result["ok"] is False
    assert any("OUTCOME_LEAKAGE" in e for e in result["errors"])


def test_validate_strategy_request_rejects_future_factor() -> None:
    bad = _base_request()
    bad["trader_view"]["factor_states"][0]["available_at"] = "2099-01-01T00:00:00Z"
    result = validate_strategy_request(bad)
    assert result["ok"] is False
    assert result["causality_errors"]


def test_forbidden_outcome_fields_matches_cmsr_set() -> None:
    assert "pnl" in FORBIDDEN_OUTCOME_FIELDS
    assert "mfe" in FORBIDDEN_OUTCOME_FIELDS
    hits = forbidden_outcome_fields({"setup": {"exit_reason": "stop"}})
    assert "setup.exit_reason" in hits


def test_london_ny_breakout_take() -> None:
    out = assess_strategy_request(_base_request())
    assert out["decision"] == "TAKE"
    assert out["research_only"] is True
    assert "TAKE_BREAKOUT_SESSION" in out["reason_codes"]


def test_london_ny_breakout_reject_wrong_session() -> None:
    req = _base_request()
    req["trader_view"]["factor_states"][0]["value"] = "ASIA"
    out = assess_strategy_request(req)
    assert out["decision"] == "REJECT"
    assert "REJECT_SESSION_NOT_BREAKOUT" in out["reason_codes"]


def test_london_ny_breakout_reject_high_cost() -> None:
    req = _base_request()
    req["costs"]["commission_r"] = 0.15
    out = assess_strategy_request(req)
    assert out["decision"] == "REJECT"
    assert "UNECONOMIC_COST_BURDEN" in out["reason_codes"]


def test_abstain_on_unknown_required_factor() -> None:
    req = _base_request()
    req["trader_view"]["factor_states"][0]["status"] = "UNKNOWN"
    out = assess_strategy_request(req)
    assert out["decision"] == "ABSTAIN"
    assert "ABSTAIN_REQUIRED_FACTOR_UNKNOWN" in out["reason_codes"]


def test_abstain_on_invalid_geometry() -> None:
    req = _base_request(strategy_id="S13_CORE")
    req["setup"]["entry"] = 1.0910
    req["setup"]["stop"] = 1.0910
    out = assess_strategy_request(req)
    assert out["decision"] == "ABSTAIN"
    assert "ABSTAIN_GEOMETRY_INVALID" in out["reason_codes"]


def test_s13_core_take_within_cost() -> None:
    req = _base_request(strategy_id="S13_CORE")
    req["trader_view"]["factor_states"] = [
        {
            "factor_id": "geometry_valid",
            "status": "AVAILABLE_HIGH",
            "value": True,
            "confidence": 0.9,
            "available_at": req["market"]["signal_time"],
            "strategy_criticality": "REQUIRED",
        },
        {
            "factor_id": "cost_burden",
            "status": "AVAILABLE_HIGH",
            "value": 0.10,
            "confidence": 0.9,
            "available_at": req["market"]["signal_time"],
            "strategy_criticality": "REQUIRED",
        },
    ]
    req["costs"]["commission_r"] = 0.10
    out = assess_strategy_request(req)
    assert out["decision"] == "TAKE"


def test_profile_registry_covers_seven_strategies() -> None:
    expected = {
        "S13_CORE",
        "SESSION_MEAN_REVERSION",
        "S14_LIQUIDITY_SWEEP",
        "LONDON_NY_BREAKOUT",
        "HTF_PULLBACK",
        "STRICT_DISPLACEMENT_FVG_RETEST",
        "FALSE_BREAK_REVERSAL_LIQUIDITY_TRAP",
    }
    assert set(PROFILE_REGISTRY.keys()) == expected


def test_assessment_output_has_no_forbidden_fields() -> None:
    out = assess_strategy_request(_base_request())
    assert forbidden_outcome_fields(out) == []
    assert out["decision"] in {"TAKE", "REJECT", "ABSTAIN"}


def test_setup_prices_not_mutated() -> None:
    req = _base_request()
    entry_before = req["setup"]["entry"]
    stop_before = req["setup"]["stop"]
    assess_strategy_request(req)
    assert req["setup"]["entry"] == entry_before
    assert req["setup"]["stop"] == stop_before


def test_validate_strategy_assessment_ok() -> None:
    req = _base_request()
    policy = assess_strategy_request(req)
    body = {
        "schema_version": STRATEGY_ASSESSMENT_SCHEMA_VERSION,
        "assessment_id": "strat_asmt_test001",
        "request_id": req["request_id"],
        "run_id": req["run_id"],
        "raw_setup_id": req["raw_setup_id"],
        "strategy": req["strategy"],
        "input_hash": "a" * 64,
        "output_hash": "b" * 64,
        "created_at_utc": "2026-07-21T12:00:00Z",
        **policy,
    }
    result = validate_strategy_assessment(body)
    assert result["ok"] is True


def test_validate_strategy_assessment_rejects_outcome() -> None:
    req = _base_request()
    policy = assess_strategy_request(req)
    body = {
        "schema_version": STRATEGY_ASSESSMENT_SCHEMA_VERSION,
        "assessment_id": "strat_asmt_test002",
        "request_id": req["request_id"],
        "run_id": req["run_id"],
        "raw_setup_id": req["raw_setup_id"],
        "strategy": req["strategy"],
        "input_hash": "a" * 64,
        "output_hash": "b" * 64,
        "created_at_utc": "2026-07-21T12:00:00Z",
        **policy,
    }
    bad = deepcopy(body)
    bad["mfe"] = 2.0
    result = validate_strategy_assessment(bad)
    assert result["ok"] is False
