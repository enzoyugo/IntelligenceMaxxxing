"""CriticAgentV1 — structured challenge of Policy 1.0.0 assessment; never mutates it."""

from __future__ import annotations

from typing import Any

from intelligence_maxxxing.domain_packs.trading.agent_bundle_v1 import (
    AGENT_BUNDLE_VERSION,
    CRITIC_SCHEMA_VERSION,
    THRESHOLDS,
)
from intelligence_maxxxing.domain_packs.trading.agents._common import (
    content_hash,
    has_forbidden_outcome_fields,
    new_id,
    pit_feature_violations,
    utc_now,
)

AGENT_ID = "CriticAgentV1"
AGENT_VERSION = "1.0.0"


class CriticAgentV1:
    agent_id = AGENT_ID
    agent_version = AGENT_VERSION

    def review(
        self,
        *,
        observation: dict[str, Any],
        assessment: dict[str, Any],
        context: dict[str, Any],
        findings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        # Critic must not see or require outcome.
        leaks = has_forbidden_outcome_fields(observation)
        pit = pit_feature_violations(observation)
        proposal = str(assessment.get("decision") or "UNKNOWN")
        objections: list[str] = []
        supporting: list[str] = []
        contradicting: list[str] = []
        unresolved: list[str] = []
        missing: list[str] = []
        dq_obj: list[str] = []
        fidelity_obj: list[str] = []
        context_obj: list[str] = []
        portfolio_obj: list[str] = []
        confidence_obj: list[str] = []
        reasons: list[str] = []

        if leaks:
            dq_obj.append("OUTCOME_FIELD_PRESENT")
            reasons.append("DATA_QUALITY_OBJECTION")
        if pit:
            dq_obj.append("POINT_IN_TIME_VIOLATION")
            reasons.append("DATA_QUALITY_OBJECTION")

        critical = [f for f in findings if str(f.get("severity")) == "CRITICAL" and f.get("anomaly_type") != "NO_ANOMALY"]
        high = [f for f in findings if str(f.get("severity")) == "HIGH"]
        for f in critical:
            contradicting.append(str(f.get("anomaly_type")))
            objections.append(f"CRITICAL:{f.get('anomaly_type')}")
        for f in high:
            unresolved.append(str(f.get("anomaly_type")))

        ctx_conf = float(context.get("context_confidence") or 0.0)
        if ctx_conf < THRESHOLDS["context_confidence_unknown_below"]:
            context_obj.append("CONTEXT_UNKNOWN")
            reasons.append("CONTEXT_OBJECTION")
        if context.get("spread_state") in {"HIGH", "EXTREME"} and proposal == "TAKE":
            contradicting.append("SPREAD_STATE_VS_TAKE")
            objections.append("SPREAD_OBJECTION")
            reasons.append("CRITIC_CHALLENGE")
        if context.get("market_data_health") == "DEGRADED":
            dq_obj.append("MARKET_DATA_DEGRADED")
            reasons.append("DATA_QUALITY_OBJECTION")

        fidelity = str((observation.get("economic_setup") or {}).get("strategy_fidelity_class") or "").upper()
        if fidelity == "PROXY" and proposal == "TAKE":
            fidelity_obj.append("PROXY_TAKE_UNSUPPORTED")
            reasons.append("FIDELITY_OBJECTION")
        if fidelity == "DEPRECATED":
            fidelity_obj.append("DEPRECATED_FIDELITY")
            reasons.append("FIDELITY_OBJECTION")

        conf = assessment.get("confidence") or assessment.get("rank_score")
        if conf is not None:
            try:
                if float(conf) < 0.4 and proposal == "TAKE":
                    confidence_obj.append("LOW_CONFIDENCE_TAKE")
                    reasons.append("CONFIDENCE_OBJECTION")
            except (TypeError, ValueError):
                missing.append("CONFIDENCE_UNPARSEABLE")

        reasons_assessment = list(assessment.get("reason_codes") or [])
        if "EVIDENCE_INSUFFICIENT" in reasons_assessment or "SAMPLE_TOO_SMALL" in reasons_assessment:
            supporting.append("POLICY_ALREADY_ABSTAINS_ON_EVIDENCE")
            if proposal in {"UNKNOWN", "DEFER_DATA_QUALITY", "SKIP"}:
                supporting.append("PROPOSAL_CONSISTENT_WITH_EVIDENCE_LIMIT")

        if not assessment.get("assessment_id"):
            missing.append("ASSESSMENT_ID")

        # Review status — critic does not majority-vote; structure only.
        if dq_obj or any(f.get("hard_gate_implication") == "DEFER_DATA_QUALITY" for f in critical):
            review_status = "DEFER_DATA_QUALITY"
            reasons.append("DEFER_DATA_QUALITY")
        elif objections or critical or fidelity_obj:
            review_status = "CHALLENGE"
            reasons.append("CRITIC_CHALLENGE")
        elif supporting and not contradicting and not objections:
            review_status = "SUPPORT"
        elif unresolved or missing:
            review_status = "INCONCLUSIVE"
        else:
            review_status = "INCONCLUSIVE"
            reasons.append("EVIDENCE_INSUFFICIENT")

        challenge_score = min(
            1.0,
            0.2 * len(critical) + 0.1 * len(high) + 0.15 * len(objections) + (0.2 if dq_obj else 0.0),
        )
        critic_confidence = round(min(1.0, 0.4 + challenge_score * 0.5), 4)

        setup = observation.get("economic_setup") or {}
        body: dict[str, Any] = {
            "schema_version": CRITIC_SCHEMA_VERSION,
            "critic_review_id": new_id("CRIT"),
            "assessment_id": assessment.get("assessment_id"),
            "economic_setup_id": setup.get("economic_setup_id"),
            "observation_id": observation.get("observation_id"),
            "agent_id": AGENT_ID,
            "agent_version": AGENT_VERSION,
            "agent_bundle_version": AGENT_BUNDLE_VERSION,
            "proposal_decision": proposal,
            "objections": objections,
            "supporting_evidence": supporting,
            "contradicting_evidence": contradicting,
            "unresolved_risks": unresolved,
            "missing_evidence": missing,
            "data_quality_objections": dq_obj,
            "fidelity_objections": fidelity_obj,
            "context_objections": context_obj,
            "portfolio_objections": portfolio_obj,
            "confidence_objections": confidence_obj,
            "critic_confidence": critic_confidence,
            "review_status": review_status,
            "reason_codes": reasons or ["CRITIC_INCONCLUSIVE"],
            "created_at_utc": utc_now(),
            "mutates_assessment": False,
            "outcome_access_count": 0,
            "research_only": True,
        }
        body["input_hash"] = content_hash(
            {
                "assessment_id": assessment.get("assessment_id"),
                "proposal": proposal,
                "context_id": context.get("context_assessment_id"),
                "finding_ids": [f.get("finding_id") for f in findings],
                "observation_id": observation.get("observation_id"),
            }
        )
        body["output_hash"] = content_hash({k: v for k, v in body.items() if k != "output_hash"})
        return body
