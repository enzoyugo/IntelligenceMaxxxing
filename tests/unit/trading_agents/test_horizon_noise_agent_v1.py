"""Unit tests for HorizonNoiseAgentV1 — observational sidecar outside frozen M2 bundle."""

from __future__ import annotations

from intelligence_maxxxing.domain_packs.trading.agent_bundle_v1 import (
    AGENT_BUNDLE_ID,
    AGENT_BUNDLE_VERSION,
)
from intelligence_maxxxing.domain_packs.trading.agents.horizon_noise_agent_v1 import (
    SCHEMA_VERSION,
    HorizonNoiseAgentV1,
)
from intelligence_maxxxing.domain_packs.trading.policy_v1 import POLICY_ID, POLICY_VERSION


def _snap(**overrides):
    base = {
        "horizon_observation_id": "HO_TEST",
        "economic_setup_id": "ES_TEST",
        "output_hash": "abc",
        "geometry": {"stop_distance_pips": 2.0, "planned_rr": 2.0},
        "microstructure": {"spread_to_stop_ratio": 0.12},
        "volatility": {"stop_to_atr_m5": 0.6, "volatility_bucket": "HIGH"},
        "context": {"session": "NY_LIKE", "higher_timeframe_alignment": "CONFLICT"},
        "breakout_quality": {
            "confirmation_status": "WICK_ONLY",
            "retest_status_at_cutoff": "NO_RETEST",
        },
        "missing_fields": [],
        "data_quality_status": "HORIZON_DATA_PARTIAL",
    }
    base.update(overrides)
    return base


def test_high_noise_ultra_short_and_no_trusted_prior():
    agent = HorizonNoiseAgentV1()
    out = agent.assess(
        observation={"observation_id": "OBS1", "economic_setup": {"economic_setup_id": "ES_TEST"}},
        pre_decision_horizon_snapshot=_snap(
            geometry={"stop_distance_pips": 1.2},
            microstructure={"spread_to_stop_ratio": 0.2},
        ),
        diagnostic_prior_trusted=False,
    )
    assert out["schema_version"] == SCHEMA_VERSION
    assert out["non_authoritative"] is True
    assert out["live_control"] is False
    assert out["decision"] is None
    assert out["outcome_access_count"] == 0
    assert "NO_TRUSTED_PRIOR" in out["reason_codes"]
    assert "SPREAD_MATERIAL_TO_STOP" in out["reason_codes"]
    assert out["expected_horizon_class"] in {"ULTRA_SHORT", "SHORT"}
    assert out["noise_exposure"] in {"HIGH", "EXTREME"}
    assert out["mutates_im_advisory"] is False


def test_htf_aligned_confirmed_breakout():
    agent = HorizonNoiseAgentV1()
    out = agent.assess(
        observation={"observation_id": "OBS2"},
        pre_decision_horizon_snapshot=_snap(
            geometry={"stop_distance_pips": 8.0},
            microstructure={"spread_to_stop_ratio": 0.03},
            volatility={"stop_to_atr_m5": 1.2, "volatility_bucket": "NORMAL"},
            context={"session": "LONDON_LIKE", "higher_timeframe_alignment": "ALIGNED"},
            breakout_quality={
                "confirmation_status": "CONFIRMED",
                "retest_status_at_cutoff": "NO_RETEST",
            },
            missing_fields=[],
            data_quality_status="HORIZON_DATA_COMPLETE",
        ),
    )
    assert "HTF_ALIGNED" in out["reason_codes"]
    assert "BREAKOUT_CLOSE_CONFIRMED" in out["reason_codes"]
    assert out["entry_quality"] == "STRONG"
    assert out["breakout_quality"] == "CONFIRMED"


def test_insufficient_data_unknown():
    agent = HorizonNoiseAgentV1()
    out = agent.assess(
        observation={},
        pre_decision_horizon_snapshot={
            "economic_setup_id": "ES_X",
            "geometry": {},
            "microstructure": {},
            "volatility": {},
            "context": {},
            "breakout_quality": {},
            "missing_fields": ["entry", "stop", "spread"],
            "data_quality_status": "HORIZON_DATA_UNTRUSTED",
        },
    )
    assert "DATA_INCOMPLETE" in out["reason_codes"]
    assert out["expected_horizon_class"] == "UNKNOWN"


def test_policy_and_bundle_untouched_constants():
    assert POLICY_ID == "IM_TRADING_DECISION_POLICY"
    assert POLICY_VERSION == "1.0.0"
    assert AGENT_BUNDLE_ID == "IM_M2_AGENT_BUNDLE"
    assert AGENT_BUNDLE_VERSION == "1.0.0"
    agent = HorizonNoiseAgentV1()
    out = agent.assess(observation={}, pre_decision_horizon_snapshot=_snap())
    assert out["frozen_policy_untouched"] == "IM_TRADING_DECISION_POLICY@1.0.0"
    assert out["frozen_bundle_untouched"] == "IM_M2_AGENT_BUNDLE@1.0.0"
    assert out["outside_frozen_m2_bundle"] is True
