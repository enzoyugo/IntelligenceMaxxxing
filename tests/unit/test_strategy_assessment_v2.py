"""Unit tests for frozen rich PIT factor strategy assessment profiles v2."""

from __future__ import annotations

from copy import deepcopy

from intelligence_maxxxing.domain_packs.trading.strategy_assessment_validate_v1 import (
    STRATEGY_REQUEST_SCHEMA_VERSION,
    forbidden_outcome_fields,
)
from intelligence_maxxxing.domain_packs.trading.strategy_profiles_v2 import (
    PROFILE_FROZEN_AT_UTC,
    PROFILE_REGISTRY,
    PROFILE_VERSION,
    assess_strategy_request_v2,
)


def _v2_factor(
    factor_id: str,
    *,
    value,
    signal_time: str = "2026-07-21T12:00:00Z",
    status: str = "AVAILABLE_HIGH",
) -> dict:
    return {
        "factor_id": factor_id,
        "status": status,
        "value": value,
        "confidence": 0.9,
        "available_at": signal_time,
        "strategy_criticality": "REQUIRED",
    }


def _base_v2_request(
    *,
    strategy_id: str = "SESSION_MEAN_REVERSION",
    session: str = "LONDON",
    volatility_percentile: float = 0.50,
    h1_trend_alignment: str = "NEUTRAL",
    stop_distance_atr: float = 1.5,
    displacement_atr: float | None = None,
) -> dict:
    signal_time = "2026-07-21T12:00:00Z"
    factor_states = [
        _v2_factor("session_context", value=session, signal_time=signal_time),
        _v2_factor("geometry_valid", value=True, signal_time=signal_time),
        _v2_factor("cost_burden", value=0.05, signal_time=signal_time),
        _v2_factor("atr_m5", value=0.0012, signal_time=signal_time),
        _v2_factor("volatility_percentile", value=volatility_percentile, signal_time=signal_time),
        _v2_factor("h1_trend_alignment", value=h1_trend_alignment, signal_time=signal_time),
        _v2_factor("stop_distance_atr", value=stop_distance_atr, signal_time=signal_time),
    ]
    if displacement_atr is not None:
        factor_states.append(
            _v2_factor("displacement_atr", value=displacement_atr, signal_time=signal_time)
        )
    return {
        "schema_version": STRATEGY_REQUEST_SCHEMA_VERSION,
        "request_id": "req_strat_v2_unit_001",
        "run_id": "run_strat_v2_unit_001",
        "raw_setup_id": "setup_strat_v2_unit_001",
        "idempotency_key": "STRAT_IDEM_v2_unit_001",
        "strategy": {
            "strategy_id": strategy_id,
            "strategy_version": "2.0.0",
            "family": strategy_id,
            "profile_version": "2.0.0",
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


def test_v2_profile_metadata() -> None:
    assert PROFILE_VERSION == "2.0.0"
    assert PROFILE_FROZEN_AT_UTC == "2026-07-31T22:00:00Z"
    assert set(PROFILE_REGISTRY.keys()) == {
        "SESSION_MEAN_REVERSION",
        "FALSE_BREAK_REVERSAL_LIQUIDITY_TRAP",
        "HTF_PULLBACK",
        "STRICT_DISPLACEMENT_FVG_RETEST",
    }


def test_session_mean_reversion_take() -> None:
    out = assess_strategy_request_v2(_base_v2_request())
    assert out["decision"] == "TAKE"
    assert out["profile_version"] == "2.0.0"
    assert "TAKE_SESSION_MR_CONTEXT" in out["reason_codes"]
    assert out["research_only"] is True


def test_session_mean_reversion_reject_extreme_volatility() -> None:
    req = _base_v2_request(volatility_percentile=0.95)
    out = assess_strategy_request_v2(req)
    assert out["decision"] == "REJECT"
    assert "REJECT_EXTREME_EXPANSION" in out["reason_codes"]


def test_session_mean_reversion_reject_with_trade_alignment() -> None:
    req = _base_v2_request(h1_trend_alignment="WITH_TRADE")
    out = assess_strategy_request_v2(req)
    assert out["decision"] == "REJECT"
    assert "REJECT_STRONG_TREND_ALIGNMENT" in out["reason_codes"]


def test_false_break_take() -> None:
    req = _base_v2_request(strategy_id="FALSE_BREAK_REVERSAL_LIQUIDITY_TRAP", session="OVERLAP")
    out = assess_strategy_request_v2(req)
    assert out["decision"] == "TAKE"
    assert "TAKE_FALSE_BREAK_CONTEXT" in out["reason_codes"]


def test_false_break_reject_wrong_session() -> None:
    req = _base_v2_request(strategy_id="FALSE_BREAK_REVERSAL_LIQUIDITY_TRAP", session="ASIA")
    out = assess_strategy_request_v2(req)
    assert out["decision"] == "REJECT"
    assert "REJECT_SESSION_NOT_BREAKOUT" in out["reason_codes"]


def test_false_break_reject_wide_stop() -> None:
    req = _base_v2_request(
        strategy_id="FALSE_BREAK_REVERSAL_LIQUIDITY_TRAP",
        stop_distance_atr=3.0,
    )
    out = assess_strategy_request_v2(req)
    assert out["decision"] == "REJECT"
    assert "REJECT_STOP_TOO_WIDE_VS_ATR" in out["reason_codes"]


def test_htf_pullback_take_neutral() -> None:
    req = _base_v2_request(strategy_id="HTF_PULLBACK", h1_trend_alignment="NEUTRAL")
    out = assess_strategy_request_v2(req)
    assert out["decision"] == "TAKE"
    assert "TAKE_HTF_PULLBACK_ALIGNED" in out["reason_codes"]


def test_htf_pullback_take_with_trade() -> None:
    req = _base_v2_request(strategy_id="HTF_PULLBACK", h1_trend_alignment="WITH_TRADE")
    out = assess_strategy_request_v2(req)
    assert out["decision"] == "TAKE"
    assert "TAKE_HTF_PULLBACK_ALIGNED" in out["reason_codes"]


def test_htf_pullback_reject_against_trade() -> None:
    req = _base_v2_request(strategy_id="HTF_PULLBACK", h1_trend_alignment="AGAINST_TRADE")
    out = assess_strategy_request_v2(req)
    assert out["decision"] == "REJECT"
    assert "REJECT_HTF_AGAINST" in out["reason_codes"]


def test_strict_fvg_take() -> None:
    req = _base_v2_request(
        strategy_id="STRICT_DISPLACEMENT_FVG_RETEST",
        displacement_atr=1.2,
    )
    out = assess_strategy_request_v2(req)
    assert out["decision"] == "TAKE"
    assert "TAKE_STRICT_FVG_DISPLACEMENT" in out["reason_codes"]


def test_strict_fvg_reject_weak_displacement() -> None:
    req = _base_v2_request(
        strategy_id="STRICT_DISPLACEMENT_FVG_RETEST",
        displacement_atr=0.5,
    )
    out = assess_strategy_request_v2(req)
    assert out["decision"] == "REJECT"
    assert "REJECT_WEAK_DISPLACEMENT" in out["reason_codes"]


def test_strict_fvg_abstain_unknown_displacement() -> None:
    req = _base_v2_request(strategy_id="STRICT_DISPLACEMENT_FVG_RETEST")
    req["trader_view"]["factor_states"].append(
        _v2_factor("displacement_atr", value=None, status="UNKNOWN")
    )
    out = assess_strategy_request_v2(req)
    assert out["decision"] == "ABSTAIN"
    assert "ABSTAIN_REQUIRED_FACTOR_UNKNOWN" in out["reason_codes"]


def test_shared_abstain_unknown_required_factor() -> None:
    req = _base_v2_request()
    for row in req["trader_view"]["factor_states"]:
        if row["factor_id"] == "atr_m5":
            row["status"] = "UNKNOWN"
    out = assess_strategy_request_v2(req)
    assert out["decision"] == "ABSTAIN"
    assert "ABSTAIN_REQUIRED_FACTOR_UNKNOWN" in out["reason_codes"]


def test_shared_abstain_invalid_geometry() -> None:
    req = _base_v2_request()
    req["setup"]["entry"] = 1.0910
    req["setup"]["stop"] = 1.0910
    out = assess_strategy_request_v2(req)
    assert out["decision"] == "ABSTAIN"
    assert "ABSTAIN_GEOMETRY_INVALID" in out["reason_codes"]


def test_shared_reject_high_cost() -> None:
    req = _base_v2_request()
    req["costs"]["commission_r"] = 0.15
    out = assess_strategy_request_v2(req)
    assert out["decision"] == "REJECT"
    assert "UNECONOMIC_COST_BURDEN" in out["reason_codes"]


def test_abstain_unknown_strategy() -> None:
    req = _base_v2_request(strategy_id="LONDON_NY_BREAKOUT")
    out = assess_strategy_request_v2(req)
    assert out["decision"] == "ABSTAIN"
    assert "ABSTAIN_UNKNOWN_STRATEGY" in out["reason_codes"]


def test_setup_prices_not_mutated() -> None:
    req = _base_v2_request()
    entry_before = req["setup"]["entry"]
    stop_before = req["setup"]["stop"]
    assess_strategy_request_v2(req)
    assert req["setup"]["entry"] == entry_before
    assert req["setup"]["stop"] == stop_before


def test_assessment_output_has_no_forbidden_fields() -> None:
    out = assess_strategy_request_v2(_base_v2_request())
    assert forbidden_outcome_fields(out) == []
    assert out["decision"] in {"TAKE", "REJECT", "ABSTAIN"}


def test_optional_factors_do_not_block_take() -> None:
    req = _base_v2_request()
    signal_time = req["market"]["signal_time"]
    req["trader_view"]["factor_states"].extend(
        [
            _v2_factor("compression_ratio", value=0.4, signal_time=signal_time),
            {
                "factor_id": "calendar_high_impact_proximity_min",
                "status": "UNKNOWN",
                "value": None,
                "confidence": 0.0,
                "available_at": signal_time,
                "strategy_criticality": "OPTIONAL",
            },
        ]
    )
    out = assess_strategy_request_v2(deepcopy(req))
    assert out["decision"] == "TAKE"
