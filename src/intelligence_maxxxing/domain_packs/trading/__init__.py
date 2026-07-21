"""Trading Pack — TMX read-only assessment (Milestone 1) + M2 agents.

TradingMaxxxing is an external HTTP client. This pack never imports TMX code,
never accesses TMX storage, and never issues broker/execution commands.
Policy 1.0.0 remains frozen; M2 agents are non-authoritative parallel artifacts.
"""

from intelligence_maxxxing.domain_packs.trading.agent_bundle_v1 import (
    AGENT_BUNDLE_ID,
    AGENT_BUNDLE_VERSION,
    BUNDLE_MANIFEST_HASH,
    active_bundle_manifest,
)
from intelligence_maxxxing.domain_packs.trading.policy_v1 import (
    POLICY_FROZEN_AT,
    POLICY_ID,
    POLICY_VERSION,
    RULESET_HASH,
    assess_observation,
)

__all__ = [
    "POLICY_ID",
    "POLICY_VERSION",
    "POLICY_FROZEN_AT",
    "RULESET_HASH",
    "assess_observation",
    "AGENT_BUNDLE_ID",
    "AGENT_BUNDLE_VERSION",
    "BUNDLE_MANIFEST_HASH",
    "active_bundle_manifest",
]
