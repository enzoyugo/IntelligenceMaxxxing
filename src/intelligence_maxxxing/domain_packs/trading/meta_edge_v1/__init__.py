"""IM Trading Meta-Edge research pack (parallel to frozen Policy 1.0.0).

Research-only. promotion_eligible=false. live_policy_influence=false.
Must not import tradingmaxxing_* or read TMX storage.
"""

from __future__ import annotations

RESEARCH_POLICY_ID = "IM_TRADING_META_EDGE_RESEARCH_POLICY@1.0.0"
RESEARCH_BUNDLE_ID = "IM_TRADING_META_EDGE_AGENT_BUNDLE@1.0.0"
PROMOTION_ELIGIBLE = False
LIVE_POLICY_INFLUENCE = False

__all__ = [
    "RESEARCH_POLICY_ID",
    "RESEARCH_BUNDLE_ID",
    "PROMOTION_ELIGIBLE",
    "LIVE_POLICY_INFLUENCE",
]
