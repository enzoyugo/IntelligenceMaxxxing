"""M2 Context / Anomaly / Critic / Shadow unit tests."""

from __future__ import annotations

from intelligence_maxxxing.domain_packs.trading.agent_bundle_v1 import (
    AGENT_BUNDLE_VERSION,
    BUNDLE_MANIFEST_HASH,
    active_bundle_manifest,
)
from intelligence_maxxxing.domain_packs.trading.agents.anomaly_agent_v1 import AnomalyAgentV1
from intelligence_maxxxing.domain_packs.trading.agents.context_agent_v1 import ContextAgentV1
from intelligence_maxxxing.domain_packs.trading.agents.critic_agent_v1 import CriticAgentV1
from intelligence_maxxxing.domain_packs.trading.agents.shadow_adjudicator_v1 import (
    M2ShadowAdjudicatorV1,
)
from intelligence_maxxxing.domain_packs.trading.policy_v1 import POLICY_VERSION, assess_observation


def _obs(**over):
    base = {
        "schema_version": "tmx.im.observation.v1",
        "experiment_id": "TMX_IM_RETROSPECTIVE_AGENT_REPLAY_V1",
        "experiment_mode": "RETROSPECTIVE_DIAGNOSTIC",
        "origin": "TRAIN",
        "observation_id": "OBS_M2_1",
        "idempotency_key": "IDEM_M2_1",
        "source_system": "TradingMaxxxing",
        "source_commit": "abc",
        "created_at_utc": "2025-03-15T12:00:00Z",
        "decision_cutoff_utc": "2025-03-15T12:00:00Z",
        "available_at_utc": "2025-03-15T12:00:00Z",
        "economic_setup": {
            "economic_setup_id": "ES_M2_1",
            "source_event_id": "E1",
            "strategy_id": "inside_bar_shadow",
            "strategy_family": "INSIDE_BAR",
            "strategy_implementation_version": "v1",
            "strategy_fidelity_class": "PARTIAL",
            "symbol": "EURUSD",
            "timeframe": "M5",
            "direction": "LONG",
            "signal_time_utc": "2025-03-15T12:00:00Z",
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
            "decision_created_at_utc": "2025-03-15T12:00:00Z",
        },
        "tmx_native": {
            "decision": "UNKNOWN",
            "reason_codes": ["SHADOW"],
            "nominal_risk_R": 1.0,
            "decision_created_at_utc": "2025-03-15T12:00:00Z",
        },
        "feature_snapshot_id": "FS1",
        "features": {
            "spread_price": {
                "value": 0.00012,
                "observed_at_utc": "2025-03-15T12:00:00Z",
                "available_at_utc": "2025-03-15T12:00:00Z",
                "source": "TEST",
                "quality": "QUOTE_VALID",
                "version": "v1",
            }
        },
        "market_context": {"symbol": "EURUSD", "session": "OVERLAP"},
        "data_quality": {"quote_quality": "QUOTE_VALID", "cost_quality": "COST_UNAVAILABLE"},
        "risk_context": {},
        "portfolio_context": {},
        "provenance": {"source": "unit_test"},
    }
    base.update(over)
    return base


def test_bundle_preregistered() -> None:
    m = active_bundle_manifest()
    assert m["agent_bundle_version"] == "1.0.0"
    assert m["manifest_hash"] == BUNDLE_MANIFEST_HASH
    assert m["live_policy_influence"] is False
    assert POLICY_VERSION == "1.0.0"


def test_context_deterministic_and_no_outcome() -> None:
    agent = ContextAgentV1()
    a = agent.assess(_obs())
    b = agent.assess(_obs())
    assert a["session"] == "OVERLAP"
    assert a["outcome_access_count"] == 0
    assert a["input_hash"] == b["input_hash"]
    assert a["feature_schema_hash"] == b["feature_schema_hash"]
    assert "BUY" not in str(a.get("reason_codes"))


def test_context_future_feature_flagged() -> None:
    obs = _obs(
        features={
            "spread_price": {
                "value": 0.0001,
                "observed_at_utc": "2025-03-15T13:00:00Z",
                "available_at_utc": "2025-03-15T13:00:00Z",
                "source": "TEST",
                "quality": "QUOTE_VALID",
                "version": "v1",
            }
        }
    )
    out = ContextAgentV1().assess(obs)
    assert out["point_in_time_violations"]


def test_anomaly_origin_violation() -> None:
    findings = AnomalyAgentV1().detect(
        _obs(origin="FORWARD", experiment_mode="RETROSPECTIVE_DIAGNOSTIC")
    )
    types = {f["anomaly_type"] for f in findings}
    assert "REPLAY_ORIGIN_VIOLATION" in types


def test_anomaly_future_quote() -> None:
    findings = AnomalyAgentV1().detect(
        _obs(data_quality={"quote_quality": "QUOTE_FUTURE_REJECTED", "cost_quality": "COST_UNAVAILABLE"})
    )
    assert any(f["anomaly_type"] == "QUOTE_FUTURE_OR_STALE" and f["severity"] == "CRITICAL" for f in findings)


def test_anomaly_duplicate() -> None:
    agent = AnomalyAgentV1()
    agent.detect(_obs())
    findings = agent.detect(_obs())
    assert any(f["anomaly_type"] == "DUPLICATE_OBSERVATION" for f in findings)


def test_critic_cannot_mutate_and_challenges() -> None:
    obs = _obs()
    assessment = {
        "assessment_id": "ASM1",
        "decision": "TAKE",
        "rank_score": 0.9,
        "reason_codes": ["SCORE_ABOVE_TAKE_THRESHOLD"],
        "economic_setup_id": "ES_M2_1",
    }
    context = ContextAgentV1().assess(obs)
    findings = AnomalyAgentV1().detect(
        _obs(data_quality={"quote_quality": "QUOTE_FUTURE_REJECTED", "cost_quality": "COST_UNAVAILABLE"})
    )
    review = CriticAgentV1().review(
        observation=obs, assessment=assessment, context=context, findings=findings
    )
    assert review["mutates_assessment"] is False
    assert review["outcome_access_count"] == 0
    assert review["proposal_decision"] == "TAKE"
    assert review["review_status"] in {"CHALLENGE", "DEFER_DATA_QUALITY"}


def test_shadow_hard_dq_dominates_and_non_authoritative() -> None:
    assessment = {
        "assessment_id": "ASM1",
        "decision": "TAKE",
        "economic_setup_id": "ES_M2_1",
        "rank_score": 0.9,
    }
    context = {"context_assessment_id": "CTX1", "context_confidence": 0.8}
    findings = [
        {
            "finding_id": "F1",
            "anomaly_type": "QUOTE_FUTURE_OR_STALE",
            "severity": "CRITICAL",
            "hard_gate_implication": "DEFER_DATA_QUALITY",
        }
    ]
    critic = {
        "critic_review_id": "C1",
        "review_status": "DEFER_DATA_QUALITY",
        "critic_confidence": 0.9,
        "economic_setup_id": "ES_M2_1",
    }
    out = M2ShadowAdjudicatorV1().adjudicate(
        assessment=assessment, context=context, findings=findings, critic=critic
    )
    assert out["shadow_recommendation"] == "DEFER_DATA_QUALITY"
    assert out["non_authoritative"] is True
    assert out["live_control"] is False
    assert out["mutates_live_policy"] is False
    assert out["agent_bundle_version"] == AGENT_BUNDLE_VERSION


def test_shadow_never_upgrades_unknown_to_take() -> None:
    out = M2ShadowAdjudicatorV1().adjudicate(
        assessment={"assessment_id": "A", "decision": "UNKNOWN", "economic_setup_id": "E"},
        context={"context_assessment_id": "C", "context_confidence": 0.99, "spread_state": "LOW"},
        findings=[{"finding_id": "F", "anomaly_type": "NO_ANOMALY", "severity": "INFO"}],
        critic={
            "critic_review_id": "R",
            "review_status": "SUPPORT",
            "critic_confidence": 0.9,
            "economic_setup_id": "E",
        },
    )
    assert out["shadow_recommendation"] != "TAKE"


def test_policy_unchanged_by_agents() -> None:
    obs = _obs()
    before = assess_observation(obs)
    ContextAgentV1().assess(obs)
    AnomalyAgentV1().detect(obs)
    after = assess_observation(obs)
    assert before["decision"] == after["decision"]
    assert POLICY_VERSION == "1.0.0"
