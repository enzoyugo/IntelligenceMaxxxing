"""M2 trading agent use cases — append-only storage; never mutates Policy 1.0.0."""

from __future__ import annotations

from typing import Any

from intelligence_maxxxing.application.errors import ApplicationError
from intelligence_maxxxing.domain_packs.trading.agent_bundle_v1 import active_bundle_manifest
from intelligence_maxxxing.domain_packs.trading.agents.anomaly_agent_v1 import AnomalyAgentV1
from intelligence_maxxxing.domain_packs.trading.agents.context_agent_v1 import ContextAgentV1
from intelligence_maxxxing.domain_packs.trading.agents.critic_agent_v1 import CriticAgentV1
from intelligence_maxxxing.domain_packs.trading.agents.orchestrator_v1 import M2AgentOrchestratorV1
from intelligence_maxxxing.domain_packs.trading.agents.shadow_adjudicator_v1 import (
    M2ShadowAdjudicatorV1,
)
from intelligence_maxxxing.infrastructure.trading.jsonl_store import TradingJsonlStore


class TradingAgentError(ApplicationError):
    code = "TRADING_AGENT_ERROR"


class TradingAgentNotFoundError(ApplicationError):
    code = "TRADING_AGENT_ARTIFACT_NOT_FOUND"


class TradingAgentService:
    def __init__(self, store: TradingJsonlStore | None = None) -> None:
        self.store = store or TradingJsonlStore()
        self.orchestrator = M2AgentOrchestratorV1()
        self.context_agent = ContextAgentV1()
        self.anomaly_agent = AnomalyAgentV1()
        self.critic_agent = CriticAgentV1()
        self.adjudicator = M2ShadowAdjudicatorV1()

    def active_bundle(self) -> dict[str, Any]:
        return active_bundle_manifest()

    def agents_health(self) -> dict[str, Any]:
        counts = self.store.agent_counts()
        return {
            "status": "ok",
            "service": "trading_agents_m2",
            "agent_bundle": self.active_bundle(),
            "ollama": {"status": "DISABLED", "required": False},
            "storage": {"backend": "jsonl", "path": str(self.store.root), **counts},
            "research_only": True,
            "non_authoritative": True,
            "live_policy_influence": False,
        }

    def create_context(self, observation: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(observation, dict):
            raise TradingAgentError("observation must be object")
        out = self.context_agent.assess(observation)
        self.store.save_context_assessment(out)
        self.store.save_agent_run(
            {
                "agent_id": "ContextAgentV1",
                "artifact_id": out.get("context_assessment_id"),
                "observation_id": observation.get("observation_id"),
                "created_at_utc": out.get("created_at_utc"),
            }
        )
        return out

    def get_context(self, context_assessment_id: str) -> dict[str, Any]:
        row = self.store.get_context_assessment(context_assessment_id)
        if not row:
            raise TradingAgentNotFoundError(f"context not found: {context_assessment_id}")
        return row

    def create_anomaly_findings(self, observation: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(observation, dict):
            raise TradingAgentError("observation must be object")
        findings = self.anomaly_agent.detect(observation)
        for f in findings:
            self.store.save_anomaly_finding(f)
        return {"findings": findings, "count": len(findings)}

    def get_anomaly(self, finding_id: str) -> dict[str, Any]:
        row = self.store.get_anomaly_finding(finding_id)
        if not row:
            raise TradingAgentNotFoundError(f"finding not found: {finding_id}")
        return row

    def create_critic_review(self, body: dict[str, Any]) -> dict[str, Any]:
        observation = body.get("observation")
        assessment = body.get("assessment")
        context = body.get("context_assessment")
        findings = body.get("anomaly_findings") or []
        if not isinstance(observation, dict) or not isinstance(assessment, dict):
            raise TradingAgentError("observation and assessment required")
        if not isinstance(context, dict):
            context = self.context_agent.assess(observation)
        if not findings:
            findings = self.anomaly_agent.detect(observation)
        out = self.critic_agent.review(
            observation=observation,
            assessment=assessment,
            context=context,
            findings=list(findings),
        )
        self.store.save_critic_review(out)
        return out

    def get_critic(self, critic_review_id: str) -> dict[str, Any]:
        row = self.store.get_critic_review(critic_review_id)
        if not row:
            raise TradingAgentNotFoundError(f"critic review not found: {critic_review_id}")
        return row

    def create_shadow_adjudication(self, body: dict[str, Any]) -> dict[str, Any]:
        assessment = body.get("assessment")
        context = body.get("context_assessment")
        findings = body.get("anomaly_findings") or []
        critic = body.get("critic_review")
        if not isinstance(assessment, dict) or not isinstance(context, dict) or not isinstance(critic, dict):
            raise TradingAgentError("assessment, context_assessment, critic_review required")
        out = self.adjudicator.adjudicate(
            assessment=assessment,
            context=context,
            findings=list(findings),
            critic=critic,
        )
        self.store.save_shadow_adjudication(out)
        return out

    def get_shadow(self, shadow_adjudication_id: str) -> dict[str, Any]:
        row = self.store.get_shadow_adjudication(shadow_adjudication_id)
        if not row:
            raise TradingAgentNotFoundError(f"shadow adjudication not found: {shadow_adjudication_id}")
        return row

    def run_bundle(self, *, observation: dict[str, Any], assessment: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(observation, dict) or not isinstance(assessment, dict):
            raise TradingAgentError("observation and assessment required")
        bundle_out = self.orchestrator.run(observation=observation, assessment=assessment)
        ctx = bundle_out["context_assessment"]
        self.store.save_context_assessment(ctx)
        for f in bundle_out["anomaly_findings"]:
            self.store.save_anomaly_finding(f)
        self.store.save_critic_review(bundle_out["critic_review"])
        self.store.save_shadow_adjudication(bundle_out["shadow_adjudication"])
        self.store.save_agent_run(
            {
                "agent_id": "M2AgentOrchestratorV1",
                "observation_id": observation.get("observation_id"),
                "assessment_id": assessment.get("assessment_id"),
                "shadow_adjudication_id": bundle_out["shadow_adjudication"].get(
                    "shadow_adjudication_id"
                ),
                "created_at_utc": bundle_out["shadow_adjudication"].get("created_at"),
            }
        )
        return bundle_out
