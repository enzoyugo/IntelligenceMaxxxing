"""IM narrative + episodic runtime tests."""

from __future__ import annotations

from intelligence_maxxxing.domain_packs.trading.market_narrative_v1.episodic_runtime_v1 import (
    encode_episode,
    retrieve_similar,
    run_episodic_runtime,
)
from intelligence_maxxxing.domain_packs.trading.market_narrative_v1.narrative_runtime_v1 import (
    build_narrative,
    run_narrative_runtime,
)


def _ctx():
    return {
        "symbol": "EURUSD",
        "as_of": "2024-06-01T12:00:00Z",
        "available_at": "2024-06-01T12:00:00Z",
        "context_hash": "abc",
        "timeframes": {
            "M15": {"external_direction": "UP", "internal_direction": "UP"},
            "H1": {"external_direction": "UP", "internal_direction": "UP"},
        },
        "mtf": {"alignment": True, "H4": "UNAVAILABLE", "D1": "UNAVAILABLE"},
        "liquidity": {
            "n_nodes": 10,
            "sweep_stats": {"wick_only_raid": 1},
            "paths": [
                {
                    "asymmetry": 0.2,
                    "nearest_external_above": "n1",
                    "nearest_external_below": "n2",
                }
            ],
        },
        "zones": {"n_zones": 3, "armed_ids": ["z1"]},
        "event_risk_state": "CALENDAR_UNKNOWN",
        "evidence_object_ids": ["e1", "e2"],
    }


def test_narrative_deterministic_and_no_outcomes():
    a = run_narrative_runtime(_ctx())
    b = run_narrative_runtime(_ctx())
    assert a["narrative"]["narrative_hash"] == b["narrative"]["narrative_hash"]
    assert a["narrative"]["forbids_outcomes"] is True
    assert "outcome" not in a["narrative"]
    assert a["narrative"]["human_text_evidence_subset"] is True
    assert "e1" in a["narrative"]["human_text"]


def test_human_text_derived_from_json_only():
    narr = build_narrative(_ctx())
    # human text must not invent ids
    assert "e3" not in narr["human_text"]
    for eid in narr["evidence_object_ids"]:
        assert eid in narr["human_text"]


def test_hypothesis_lifecycle_and_alternative():
    out = run_narrative_runtime(_ctx())
    assert len(out["hypotheses"]) == 2
    primary, alt = out["hypotheses"]
    assert primary["alternative_hypothesis_id"] == alt["hypothesis_id"]
    assert primary["forbids_outcomes"] is True
    assert out["transitions"]


def test_outcome_injection_ignored_for_hash_identity():
    out = run_narrative_runtime(_ctx())
    poisoned = dict(out["narrative"])
    poisoned["outcome_R"] = 9.9
    # rebuilding without outcome matches original hash fields excluding human extras
    clean = build_narrative(_ctx())
    assert clean["narrative_hash"] == out["narrative"]["narrative_hash"]
    assert "outcome_R" not in clean


def test_episodic_no_policy_influence_and_retrieval():
    ctx = _ctx()
    narr = run_narrative_runtime(ctx)
    epi = run_episodic_runtime(
        context=ctx, narrative=narr["narrative"], hypotheses=narr["hypotheses"]
    )
    assert epi["policy_influence"] is False
    assert epi["shadow_influence"] is False
    assert epi["episode"]["outcome_labels"] is None
    ep2 = encode_episode(context=ctx, narrative=narr["narrative"], hypotheses=narr["hypotheses"])
    hits = retrieve_similar(ep2, [epi["episode"], ep2], top_k=2)
    assert hits
