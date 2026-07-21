"""M2 trading agents — Context, Anomaly, Critic, Shadow Adjudicator."""

from intelligence_maxxxing.domain_packs.trading.agents.anomaly_agent_v1 import AnomalyAgentV1
from intelligence_maxxxing.domain_packs.trading.agents.context_agent_v1 import ContextAgentV1
from intelligence_maxxxing.domain_packs.trading.agents.critic_agent_v1 import CriticAgentV1
from intelligence_maxxxing.domain_packs.trading.agents.shadow_adjudicator_v1 import (
    M2ShadowAdjudicatorV1,
)

__all__ = [
    "ContextAgentV1",
    "AnomalyAgentV1",
    "CriticAgentV1",
    "M2ShadowAdjudicatorV1",
]
