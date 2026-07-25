"""Research-only agent bundle parallel to frozen M2 Bundle 1.0.0."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from intelligence_maxxxing.domain_packs.trading.meta_edge_v1 import (
    LIVE_POLICY_INFLUENCE,
    PROMOTION_ELIGIBLE,
    RESEARCH_BUNDLE_ID,
)


def research_bundle_manifest() -> dict[str, Any]:
    return {
        "bundle_id": RESEARCH_BUNDLE_ID,
        "promotion_eligible": PROMOTION_ELIGIBLE,
        "live_policy_influence": LIVE_POLICY_INFLUENCE,
        "authoritative_for_im_advisory": False,
        "agents": [
            {
                "agent_id": "MetaEdgeBaseRateAgentV1",
                "role": "expected_net_R_lookup",
                "can_emit_take_skip": True,
                "research_only": True,
            },
            {
                "agent_id": "MetaEdgeRidgeExpectancyAgentV1",
                "role": "diagnostic_expectancy_model",
                "can_emit_take_skip": False,
                "research_only": True,
            },
            {
                "agent_id": "MetaEdgeSampleGateAgentV1",
                "role": "min_n_and_uncertainty",
                "can_emit_take_skip": False,
                "research_only": True,
            },
        ],
        "notes": [
            "Parallel to IM_M2_AGENT_BUNDLE@1.0.0 — must not mutate frozen bundle.",
            "Does not influence live IM_ADVISORY.",
        ],
    }


def research_bundle_hash() -> str:
    return hashlib.sha256(
        json.dumps(research_bundle_manifest(), sort_keys=True).encode("utf-8")
    ).hexdigest()
