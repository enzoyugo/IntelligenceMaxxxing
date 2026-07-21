"""M2ShadowAdjudicatorV1 — non-authoritative parallel artifact; never mutates Policy 1.0.0."""

from __future__ import annotations

from typing import Any

from intelligence_maxxxing.domain_packs.trading.agent_bundle_v1 import (
    AGENT_BUNDLE_VERSION,
    SHADOW_ADJUDICATION_SCHEMA_VERSION,
)
from intelligence_maxxxing.domain_packs.trading.agents._common import content_hash, new_id, utc_now

AGENT_ID = "M2ShadowAdjudicatorV1"
AGENT_VERSION = "1.0.0"


class M2ShadowAdjudicatorV1:
    agent_id = AGENT_ID
    agent_version = AGENT_VERSION

    def adjudicate(
        self,
        *,
        assessment: dict[str, Any],
        context: dict[str, Any],
        findings: list[dict[str, Any]],
        critic: dict[str, Any],
    ) -> dict[str, Any]:
        base = str(assessment.get("decision") or "UNKNOWN")
        reasons: list[str] = ["NON_AUTHORITATIVE_SHADOW"]
        evidence_refs = [
            f"assessment:{assessment.get('assessment_id')}",
            f"context:{context.get('context_assessment_id')}",
            f"critic:{critic.get('critic_review_id')}",
        ]
        for f in findings:
            if f.get("finding_id"):
                evidence_refs.append(f"finding:{f.get('finding_id')}")

        hard_dq = False
        critical_defer = False
        for f in findings:
            impl = str(f.get("hard_gate_implication") or "")
            if impl in {"DEFER_DATA_QUALITY", "REJECT_ROW"}:
                hard_dq = True
            if str(f.get("severity")) == "CRITICAL" and impl == "DEFER":
                critical_defer = True
            if str(f.get("anomaly_type")) == "REPLAY_ORIGIN_VIOLATION":
                hard_dq = True

        review_status = str(critic.get("review_status") or "")
        shadow = base
        status = "UPHOLD"
        confidence = 0.5

        # Hard DQ always dominates.
        if hard_dq or review_status == "DEFER_DATA_QUALITY":
            shadow = "DEFER_DATA_QUALITY"
            status = "DEFER"
            reasons.append("HARD_DQ_GATE")
            confidence = 0.9
        elif critical_defer:
            shadow = "DEFER_DATA_QUALITY"
            status = "DEFER"
            reasons.append("ANOMALY_CRITICAL_DEFER")
            confidence = 0.85
        elif review_status == "CHALLENGE":
            if base == "TAKE":
                shadow = "SKIP"
                status = "DOWNGRADE"
                reasons.append("CRITIC_CHALLENGE")
                confidence = float(critic.get("critic_confidence") or 0.6)
            elif base in {"UNKNOWN", "DEFER_DATA_QUALITY"}:
                # Never elevate UNKNOWN to TAKE from context alone.
                shadow = base
                status = "CHALLENGE"
                reasons.append("CRITIC_CHALLENGE")
                reasons.append("UNKNOWN_NOT_UPGRADED")
                confidence = float(critic.get("critic_confidence") or 0.55)
            else:
                shadow = base
                status = "CHALLENGE"
                reasons.append("CRITIC_CHALLENGE")
                confidence = float(critic.get("critic_confidence") or 0.55)
        elif review_status == "SUPPORT":
            shadow = base
            status = "UPHOLD"
            confidence = 0.6
            reasons.append("CRITIC_SUPPORT")
        else:
            # INCONCLUSIVE / insufficient evidence
            if base == "TAKE" and (context.get("context_confidence") or 0) < 0.25:
                shadow = "UNKNOWN"
                status = "DOWNGRADE"
                reasons.append("EVIDENCE_INSUFFICIENT")
                reasons.append("CONTEXT_UNKNOWN")
                confidence = 0.45
            else:
                shadow = base if base != "TAKE" or float(assessment.get("rank_score") or 0) >= 0.55 else "UNKNOWN"
                if shadow != base:
                    status = "DOWNGRADE"
                    reasons.append("EVIDENCE_INSUFFICIENT")
                else:
                    status = "UPHOLD"
                confidence = 0.4
                reasons.append("INCONCLUSIVE")

        # Absolute: never upgrade UNKNOWN → TAKE via context.
        if base in {"UNKNOWN", "DEFER_DATA_QUALITY"} and shadow == "TAKE":
            shadow = base
            status = "UPHOLD"
            reasons.append("UNKNOWN_NOT_UPGRADED")

        body: dict[str, Any] = {
            "schema_version": SHADOW_ADJUDICATION_SCHEMA_VERSION,
            "shadow_adjudication_id": new_id("SHAD"),
            "economic_setup_id": assessment.get("economic_setup_id")
            or critic.get("economic_setup_id"),
            "base_policy_decision": base,
            "shadow_recommendation": shadow,
            "status": status,
            "confidence": round(float(confidence), 4),
            "reason_codes": reasons,
            "evidence_refs": evidence_refs,
            "agent_id": AGENT_ID,
            "agent_version": AGENT_VERSION,
            "agent_bundle_version": AGENT_BUNDLE_VERSION,
            "non_authoritative": True,
            "promotion_eligible": False,
            "live_control": False,
            "mutates_live_policy": False,
            "created_at": utc_now(),
            "research_only": True,
        }
        body["input_hash"] = content_hash(
            {
                "assessment_id": assessment.get("assessment_id"),
                "base": base,
                "critic_status": review_status,
                "finding_ids": [f.get("finding_id") for f in findings],
            }
        )
        body["output_hash"] = content_hash({k: v for k, v in body.items() if k != "output_hash"})
        return body
