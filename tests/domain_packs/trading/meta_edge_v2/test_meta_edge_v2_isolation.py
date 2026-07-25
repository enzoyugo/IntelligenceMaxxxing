from __future__ import annotations

from pathlib import Path

from intelligence_maxxxing.domain_packs.trading.meta_edge_v2 import (
    LIVE_POLICY_INFLUENCE,
    PROMOTION_ELIGIBLE,
    RESEARCH_POLICY_ID,
)


def test_v2_not_promotable():
    assert PROMOTION_ELIGIBLE is False
    assert LIVE_POLICY_INFLUENCE is False
    assert "V2" in RESEARCH_POLICY_ID


def test_frozen_policy_untouched():
    policy = (
        Path(__file__).resolve().parents[4]
        / "src/intelligence_maxxxing/domain_packs/trading/policy_v1.py"
    )
    text = policy.read_text(encoding="utf-8")
    assert "META_EDGE_RESEARCH_POLICY_V2" not in text
