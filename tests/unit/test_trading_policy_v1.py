"""IM trading policy 1.0.0 unit tests."""

from __future__ import annotations

from intelligence_maxxxing.domain_packs.trading.policy_v1 import (
    POLICY_VERSION,
    RULESET_HASH,
    assess_observation,
)


def _obs(**over):
    base = {
        "schema_version": "tmx.im.observation.v1",
        "experiment_id": "TMX_IM_TRIPLE_LANE_PROSPECTIVE_V1",
        "observation_id": "OBS1",
        "idempotency_key": "IDEM1",
        "source_system": "TradingMaxxxing",
        "source_commit": "abc",
        "created_at_utc": "2026-07-21T01:00:00Z",
        "decision_cutoff_utc": "2026-07-21T01:00:00Z",
        "available_at_utc": "2026-07-21T01:00:00Z",
        "economic_setup": {
            "economic_setup_id": "ES1",
            "source_event_id": "E1",
            "strategy_id": "s14_shadow",
            "strategy_family": "S14",
            "strategy_implementation_version": "v1",
            "strategy_fidelity_class": "PARTIAL",
            "symbol": "EURUSD",
            "timeframe": "M5",
            "direction": "LONG",
            "signal_time_utc": "2026-07-21T01:00:00Z",
            "order_type": "STOP",
            "entry": 1.1,
            "stop": 1.09,
            "target": 1.12,
            "setup_geometry_hash": "g",
            "config_hash": "c",
            "nominal_risk_R": 1.0,
        },
        "raw_strategy": {
            "decision": "TAKE",
            "reason_codes": ["SOURCE"],
            "nominal_risk_R": 1.0,
            "decision_created_at_utc": "2026-07-21T01:00:00Z",
        },
        "tmx_native": {
            "decision": "UNKNOWN",
            "reason_codes": ["SHADOW"],
            "nominal_risk_R": 1.0,
            "decision_created_at_utc": "2026-07-21T01:00:00Z",
        },
        "feature_snapshot_id": "FS1",
        "features": {},
        "market_context": {"symbol": "EURUSD"},
        "data_quality": {"quote_quality": "QUOTE_VALID", "cost_quality": "COST_UNAVAILABLE"},
        "risk_context": {},
        "portfolio_context": {},
        "provenance": {},
    }
    base.update(over)
    return base


def test_policy_frozen_identity() -> None:
    assert POLICY_VERSION == "1.0.0"
    assert len(RULESET_HASH) == 64


def test_quote_missing_defers() -> None:
    out = assess_observation(_obs(data_quality={"quote_quality": "QUOTE_UNAVAILABLE"}))
    assert out["decision"] == "DEFER_DATA_QUALITY"
    assert "QUOTE_QUALITY_GATE" in out["reason_codes"] or any(
        "QUOTE" in r for r in out["reason_codes"]
    )


def test_outcome_leak_defers() -> None:
    out = assess_observation(_obs(outcome={"exit_reason": "TP"}))
    assert out["decision"] == "DEFER_DATA_QUALITY"
    assert any("OUTCOME" in r or "LEAK" in r for r in out["reason_codes"])


def test_future_feature_defers() -> None:
    out = assess_observation(
        _obs(
            features={
                "x": {
                    "value": 1,
                    "observed_at_utc": "2026-07-21T01:00:00Z",
                    "available_at_utc": "2026-07-21T03:00:00Z",
                    "source": "t",
                    "quality": "OK",
                    "version": "v1",
                }
            }
        )
    )
    assert out["decision"] == "DEFER_DATA_QUALITY"


def test_unknown_not_confidence_zero() -> None:
    out = assess_observation(_obs())
    # Evidence insufficient → UNKNOWN with null overall confidence
    if out["decision"] == "UNKNOWN":
        assert out["overall_confidence"] is None
    assert "NOT_A_WIN_PROBABILITY" in out["confidence_components"]["limitations"]


def test_idempotent_service(tmp_path) -> None:
    from intelligence_maxxxing.application.use_cases.trading_assessment import TradingAssessmentService
    from intelligence_maxxxing.infrastructure.trading.jsonl_store import TradingJsonlStore

    svc = TradingAssessmentService(TradingJsonlStore(tmp_path))
    a = svc.assess(_obs())
    b = svc.assess(_obs())
    assert a["assessment_id"] == b["assessment_id"]
    # conflict
    import pytest
    from intelligence_maxxxing.application.errors import IdempotencyConflictError

    with pytest.raises(IdempotencyConflictError):
        svc.assess(_obs(created_at_utc="2099-01-01T00:00:00Z"))
