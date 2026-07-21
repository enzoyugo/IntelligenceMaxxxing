"""Run M2 agent bundle after Policy 1.0.0 assessment (parallel artifacts)."""

from __future__ import annotations

from typing import Any

from intelligence_maxxxing.domain_packs.trading.agents.anomaly_agent_v1 import AnomalyAgentV1
from intelligence_maxxxing.domain_packs.trading.agents.context_agent_v1 import ContextAgentV1
from intelligence_maxxxing.domain_packs.trading.agents.critic_agent_v1 import CriticAgentV1
from intelligence_maxxxing.domain_packs.trading.agents.shadow_adjudicator_v1 import (
    M2ShadowAdjudicatorV1,
)
from intelligence_maxxxing.domain_packs.trading.agent_bundle_v1 import active_bundle_manifest


class M2AgentOrchestratorV1:
    def __init__(self) -> None:
        self.context_agent = ContextAgentV1()
        self.anomaly_agent = AnomalyAgentV1()
        self.critic_agent = CriticAgentV1()
        self.adjudicator = M2ShadowAdjudicatorV1()

    def run(
        self,
        *,
        observation: dict[str, Any],
        assessment: dict[str, Any],
    ) -> dict[str, Any]:
        context = self.context_agent.assess(observation)
        findings = self.anomaly_agent.detect(observation)
        critic = self.critic_agent.review(
            observation=observation,
            assessment=assessment,
            context=context,
            findings=findings,
        )
        shadow = self.adjudicator.adjudicate(
            assessment=assessment,
            context=context,
            findings=findings,
            critic=critic,
        )
        return {
            "agent_bundle": active_bundle_manifest(),
            "context_assessment": context,
            "anomaly_findings": findings,
            "critic_review": critic,
            "shadow_adjudication": shadow,
            "non_authoritative": True,
            "live_policy_influence": False,
            "research_only": True,
        }
