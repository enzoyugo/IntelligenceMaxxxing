"""IM Trading Meta-Edge research policy V2 (parallel; does not mutate Policy 1.0.0).

Reuses meta_edge_v1 train/infer machinery with a distinct policy identifier for
canonical-label campaigns. promotion_eligible=false. live_policy_influence=false.
"""

from __future__ import annotations

RESEARCH_POLICY_ID = "IM_TRADING_META_EDGE_RESEARCH_POLICY_V2@1.0.0"
RESEARCH_BUNDLE_ID = "IM_TRADING_META_EDGE_AGENT_BUNDLE_V2@1.0.0"
PROMOTION_ELIGIBLE = False
LIVE_POLICY_INFLUENCE = False

# Semantic thresholds identical to V1 thin policy (no opportunistic recalibration).
TAKE_THRESHOLD_NET_R = 0.05
SKIP_THRESHOLD_NET_R = -0.05
MIN_EVIDENCE_N = 30

__all__ = [
    "RESEARCH_POLICY_ID",
    "RESEARCH_BUNDLE_ID",
    "PROMOTION_ELIGIBLE",
    "LIVE_POLICY_INFLUENCE",
    "TAKE_THRESHOLD_NET_R",
    "SKIP_THRESHOLD_NET_R",
    "MIN_EVIDENCE_N",
]
