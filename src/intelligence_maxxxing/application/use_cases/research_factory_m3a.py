"""M3A Research Factory use cases — append-only, manual approval, no auto-run."""

from __future__ import annotations

from typing import Any

from intelligence_maxxxing.application.errors import ApplicationError
from intelligence_maxxxing.domain_packs.research_factory_m3a.constants import (
    AGENT_ALLOWED_HYPOTHESIS_STATUS,
    EVIDENCE_DIRECTIONS,
    EVIDENCE_TYPES,
    EXPERIMENT_SCHEMA,
    EXPERIMENT_STATUSES,
    EVIDENCE_SCHEMA,
    HYPOTHESIS_SCHEMA,
    HYPOTHESIS_STATUSES,
    LEARNING_SCHEMA,
    M3A_VERSION,
    MAX_AGENT_PROPOSALS_PER_CYCLE,
    RESEARCH_FACTORY_ID,
)
from intelligence_maxxxing.domain_packs.research_factory_m3a.hashes import content_hash, new_id, utc_now
from intelligence_maxxxing.domain_packs.research_factory_m3a.information_value_v1 import (
    score_information_value,
)
from intelligence_maxxxing.infrastructure.research_factory.jsonl_store import ResearchFactoryStore


class ResearchFactoryError(ApplicationError):
    code = "RESEARCH_FACTORY_ERROR"


class ResearchFactoryNotFoundError(ApplicationError):
    code = "RESEARCH_FACTORY_NOT_FOUND"


class ResearchFactoryService:
    def __init__(self, store: ResearchFactoryStore | None = None) -> None:
        self.store = store or ResearchFactoryStore()
        self._agent_proposals_cycle = 0

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "research_factory_m3a",
            "research_factory_id": RESEARCH_FACTORY_ID,
            "m3a_version": M3A_VERSION,
            "storage": {"backend": "jsonl", "path": str(self.store.root), **self.store.counts()},
            "auto_run": False,
            "auto_promotion": False,
            "live_policy_influence": False,
            "manual_approval_required": True,
            "research_only": True,
            "milestone_3_complete": False,
            "note": "M3A foundation only — not full Research Factory",
        }

    def create_hypothesis(self, body: dict[str, Any], *, actor: str = "human") -> dict[str, Any]:
        status = str(body.get("status") or "DRAFT").upper()
        if status not in HYPOTHESIS_STATUSES:
            raise ResearchFactoryError(f"invalid hypothesis status: {status}")
        created_from_agent = bool(body.get("created_from_agent") or actor == "agent")
        if created_from_agent:
            if status != AGENT_ALLOWED_HYPOTHESIS_STATUS:
                raise ResearchFactoryError("agents may only propose DRAFT hypotheses")
            self._agent_proposals_cycle += 1
            if self._agent_proposals_cycle > MAX_AGENT_PROPOSALS_PER_CYCLE:
                raise ResearchFactoryError("max agent proposals per cycle exceeded")
        hid = str(body.get("hypothesis_id") or new_id("HYP"))
        row = {
            "schema_version": HYPOTHESIS_SCHEMA,
            "hypothesis_id": hid,
            "title": body.get("title") or "untitled",
            "description": body.get("description") or "",
            "domain": body.get("domain") or "trading",
            "scope": body.get("scope") or "advisory",
            "strategy_ids": list(body.get("strategy_ids") or []),
            "fidelity_scope": list(body.get("fidelity_scope") or []),
            "symbols": list(body.get("symbols") or []),
            "sessions": list(body.get("sessions") or []),
            "regimes": list(body.get("regimes") or []),
            "created_at": utc_now(),
            "created_by": body.get("created_by") or actor,
            "source": body.get("source") or "manual",
            "status": status,
            "claim_type": body.get("claim_type") or "DIAGNOSTIC",
            "expected_direction": body.get("expected_direction"),
            "falsification_criteria": body.get("falsification_criteria") or [],
            "minimum_evidence_requirements": body.get("minimum_evidence_requirements") or [],
            "success_criteria": body.get("success_criteria") or [],
            "failure_criteria": body.get("failure_criteria") or [],
            "data_requirements": body.get("data_requirements") or {},
            "known_confounders": body.get("known_confounders") or [],
            "evidence_for_refs": list(body.get("evidence_for_refs") or []),
            "evidence_against_refs": list(body.get("evidence_against_refs") or []),
            "experiment_refs": list(body.get("experiment_refs") or []),
            "confidence": body.get("confidence"),
            "uncertainty": body.get("uncertainty"),
            "version": int(body.get("version") or 1),
            "parent_hypothesis_id": body.get("parent_hypothesis_id"),
            "supersedes": body.get("supersedes"),
            "created_from_agent": created_from_agent,
            "manual_approval_required": True,
            "m3a_version": M3A_VERSION,
            "research_only": True,
            "live_control": False,
        }
        row["input_hash"] = content_hash({k: body.get(k) for k in sorted(body.keys())})
        row["content_hash"] = content_hash({k: v for k, v in row.items() if k != "content_hash"})
        self.store.append_hypothesis(row)
        self.store.append_audit(
            {"action": "CREATE_HYPOTHESIS", "hypothesis_id": hid, "actor": actor, "at": utc_now()}
        )
        return row

    def list_hypotheses(self, limit: int = 100) -> dict[str, Any]:
        rows = self.store.list_hypotheses(limit=limit)
        return {"hypotheses": rows, "count": len(rows)}

    def get_hypothesis(self, hypothesis_id: str) -> dict[str, Any]:
        row = self.store.get_hypothesis(hypothesis_id)
        if not row:
            raise ResearchFactoryNotFoundError(f"hypothesis not found: {hypothesis_id}")
        return row

    def create_evidence(self, body: dict[str, Any], *, actor: str = "human") -> dict[str, Any]:
        direction = str(body.get("direction") or "NEUTRAL").upper()
        etype = str(body.get("evidence_type") or "EXTERNAL_STATIC_EVIDENCE").upper()
        if direction not in EVIDENCE_DIRECTIONS:
            raise ResearchFactoryError(f"invalid evidence direction: {direction}")
        if etype not in EVIDENCE_TYPES:
            raise ResearchFactoryError(f"invalid evidence type: {etype}")
        eid = str(body.get("evidence_id") or new_id("EVD"))
        row = {
            "schema_version": EVIDENCE_SCHEMA,
            "evidence_id": eid,
            "hypothesis_id": body.get("hypothesis_id"),
            "evidence_type": etype,
            "direction": direction,
            "source_system": body.get("source_system") or "IntelligenceMaxxxing",
            "source_artifact": body.get("source_artifact"),
            "source_commit": body.get("source_commit"),
            "source_hash": body.get("source_hash"),
            "experiment_id": body.get("experiment_id"),
            "economic_setup_ids": list(body.get("economic_setup_ids") or []),
            "strategy_fidelity_scope": body.get("strategy_fidelity_scope") or {},
            "time_range": body.get("time_range") or {},
            "origin": body.get("origin"),
            "sample_counts": body.get("sample_counts") or {},
            "n_raw": body.get("n_raw"),
            "n_unique": body.get("n_unique"),
            "n_trusted": body.get("n_trusted"),
            "n_effective": body.get("n_effective"),
            "quote_coverage": body.get("quote_coverage"),
            "cost_coverage": body.get("cost_coverage"),
            "temporal_validity": body.get("temporal_validity"),
            "summary": body.get("summary") or "",
            "structured_metrics": body.get("structured_metrics") or {},
            "limitations": list(body.get("limitations") or []),
            "confidence": body.get("confidence"),
            "created_at": utc_now(),
            "available_at": body.get("available_at") or utc_now(),
            "agent_id": body.get("agent_id"),
            "agent_version": body.get("agent_version"),
            "human_review_status": body.get("human_review_status") or "UNREVIEWED",
            "fixture_or_canary": bool(body.get("fixture_or_canary")),
            "retrospective_or_prospective": body.get("retrospective_or_prospective") or "UNSPECIFIED",
            "m3a_version": M3A_VERSION,
            "research_only": True,
            "created_by": actor,
        }
        row["content_hash"] = content_hash({k: v for k, v in row.items() if k != "content_hash"})
        self.store.append_evidence(row)
        self.store.append_audit(
            {"action": "CREATE_EVIDENCE", "evidence_id": eid, "actor": actor, "at": utc_now()}
        )
        return row

    def list_evidence(self, *, limit: int = 200, hypothesis_id: str | None = None) -> dict[str, Any]:
        rows = self.store.list_evidence(limit=limit, hypothesis_id=hypothesis_id)
        return {"evidence": rows, "count": len(rows)}

    def get_evidence(self, evidence_id: str) -> dict[str, Any]:
        row = self.store.get_evidence(evidence_id)
        if not row:
            raise ResearchFactoryNotFoundError(f"evidence not found: {evidence_id}")
        return row

    def create_experiment(self, body: dict[str, Any], *, actor: str = "human") -> dict[str, Any]:
        status = str(body.get("status") or "DRAFT").upper()
        if status not in EXPERIMENT_STATUSES:
            raise ResearchFactoryError(f"invalid experiment status: {status}")
        if status == "MANUALLY_APPROVED":
            raise ResearchFactoryError("use manual approval endpoint to approve experiments")
        if status == "RUNNING" and not body.get("force_illegal"):
            raise ResearchFactoryError("auto_run forbidden; cannot create RUNNING experiment")
        eid = str(body.get("experiment_id") or new_id("EXP"))
        row = {
            "schema_version": EXPERIMENT_SCHEMA,
            "experiment_id": eid,
            "hypothesis_id": body.get("hypothesis_id"),
            "title": body.get("title") or "untitled experiment",
            "mode": body.get("mode") or "RETROSPECTIVE_DIAGNOSTIC",
            "status": status,
            "pre_registration_version": body.get("pre_registration_version") or "1.0.0",
            "created_at": utc_now(),
            "approved_at": None,
            "approved_by": None,
            "start_at": body.get("start_at"),
            "end_at": body.get("end_at"),
            "strategy_fidelity_scope": body.get("strategy_fidelity_scope") or {},
            "dataset_origins": list(body.get("dataset_origins") or ["TRAIN", "VALIDATION"]),
            "split_manifest": body.get("split_manifest") or {},
            "feature_allowlist": list(body.get("feature_allowlist") or []),
            "feature_denylist": list(body.get("feature_denylist") or []),
            "policy_versions": list(body.get("policy_versions") or ["IM_TRADING_DECISION_POLICY@1.0.0"]),
            "agent_bundle_versions": list(body.get("agent_bundle_versions") or ["IM_M2_AGENT_BUNDLE@1.0.0"]),
            "primary_metric": body.get("primary_metric") or "trusted_net_R_expectancy",
            "secondary_metrics": list(body.get("secondary_metrics") or []),
            "sample_gates": body.get("sample_gates") or {"min_trusted_setups": 20},
            "dq_gates": body.get("dq_gates") or {},
            "success_criteria": list(body.get("success_criteria") or []),
            "failure_criteria": list(body.get("failure_criteria") or []),
            "stopping_rules": body.get("stopping_rules") or {},
            "resource_budget": body.get("resource_budget") or {"max_workers": 1},
            "oos_policy": "CLOSED",
            "forward_policy": "OBSERVE_ONLY_NO_TRAIN",
            "outcome_authority": "TradingMaxxxing",
            "promotion_eligible": False,
            "auto_run": False,
            "results_refs": list(body.get("results_refs") or []),
            "limitations": list(body.get("limitations") or []),
            "m3a_version": M3A_VERSION,
            "research_only": True,
            "live_policy_influence": False,
            "created_by": actor,
            "version": int(body.get("version") or 1),
        }
        if status == "PRE_REGISTERED":
            row["pre_registration_frozen_at"] = utc_now()
        row["content_hash"] = content_hash({k: v for k, v in row.items() if k != "content_hash"})
        self.store.append_experiment(row)
        self.store.append_audit(
            {"action": "CREATE_EXPERIMENT", "experiment_id": eid, "actor": actor, "at": utc_now()}
        )
        return row

    def list_experiments(self, limit: int = 100) -> dict[str, Any]:
        rows = self.store.list_experiments(limit=limit)
        return {"experiments": rows, "count": len(rows)}

    def get_experiment(self, experiment_id: str) -> dict[str, Any]:
        row = self.store.get_experiment(experiment_id)
        if not row:
            raise ResearchFactoryNotFoundError(f"experiment not found: {experiment_id}")
        return row

    def manually_approve_experiment(
        self,
        experiment_id: str,
        *,
        actor: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != "I_CONFIRM_MANUAL_APPROVAL":
            raise ResearchFactoryError("explicit confirmation required")
        if not actor or actor in {"agent", "system", "ollama"}:
            raise ResearchFactoryError("human actor required for manual approval")
        current = self.get_experiment(experiment_id)
        if current.get("status") not in {"PRE_REGISTERED", "REVIEW_REQUIRED"}:
            raise ResearchFactoryError(
                f"cannot approve from status {current.get('status')}; need PRE_REGISTERED/REVIEW_REQUIRED"
            )
        # Append new version — never destructive update.
        approved = {
            **current,
            "status": "MANUALLY_APPROVED",
            "approved_at": utc_now(),
            "approved_by": actor,
            "version": int(current.get("version") or 1) + 1,
            "auto_run": False,
            "promotion_eligible": False,
            "live_policy_influence": False,
        }
        approved["content_hash"] = content_hash(
            {k: v for k, v in approved.items() if k != "content_hash"}
        )
        self.store.append_experiment(approved)
        self.store.append_approval(
            {
                "experiment_id": experiment_id,
                "actor": actor,
                "approved_at": approved["approved_at"],
                "from_status": current.get("status"),
                "to_status": "MANUALLY_APPROVED",
                "content_hash": approved["content_hash"],
            }
        )
        self.store.append_audit(
            {
                "action": "MANUAL_APPROVE_EXPERIMENT",
                "experiment_id": experiment_id,
                "actor": actor,
                "at": utc_now(),
            }
        )
        return approved

    def create_learning(self, body: dict[str, Any], *, actor: str = "human") -> dict[str, Any]:
        lid = str(body.get("learning_id") or new_id("LRN"))
        row = {
            "schema_version": LEARNING_SCHEMA,
            "learning_id": lid,
            "source_hypothesis": body.get("source_hypothesis"),
            "source_evidence": body.get("source_evidence"),
            "source_experiment": body.get("source_experiment"),
            "what_was_believed_before": body.get("what_was_believed_before"),
            "what_was_observed": body.get("what_was_observed"),
            "what_changed": body.get("what_changed"),
            "what_did_not_change": body.get("what_did_not_change"),
            "confidence_before": body.get("confidence_before"),
            "confidence_after": body.get("confidence_after"),
            "contradictions": list(body.get("contradictions") or []),
            "open_questions": list(body.get("open_questions") or []),
            "decision_taken": body.get("decision_taken"),
            "decision_not_taken": body.get("decision_not_taken"),
            "policy_implication": body.get("policy_implication") or "NONE",
            "promotion_status": "NOT_PROMOTED",
            "created_at": utc_now(),
            "created_by": actor,
            "version": int(body.get("version") or 1),
            "m3a_version": M3A_VERSION,
            "research_only": True,
            "negative_learning_retained": True,
        }
        if not (row["source_hypothesis"] or row["source_evidence"] or row["source_experiment"]):
            raise ResearchFactoryError("learning entry requires source refs")
        row["content_hash"] = content_hash({k: v for k, v in row.items() if k != "content_hash"})
        self.store.append_learning(row)
        return row

    def list_learning(self, limit: int = 100) -> dict[str, Any]:
        rows = self.store.list_learning(limit=limit)
        return {"learning_memory": rows, "count": len(rows)}

    def priorities(self) -> dict[str, Any]:
        hyps = self.store.list_hypotheses(limit=50)
        scored = []
        for h in hyps:
            iv = score_information_value(
                {
                    "uncertainty_reduction": 0.55 if h.get("status") == "DRAFT" else 0.4,
                    "decision_relevance": 0.5,
                    "data_quality_readiness": 0.35,
                    "feasibility": 0.6,
                    "sample_gap": 0.7,
                    "novelty": 0.45,
                    "contradiction_value": 0.4,
                    "leakage_risk": 0.15,
                    "fidelity_readiness": 0.4,
                    "resource_cost": 0.35,
                    "time_cost": 0.35,
                }
            )
            scored.append({"hypothesis_id": h.get("hypothesis_id"), "title": h.get("title"), **iv})
        scored.sort(key=lambda x: float(x.get("information_value_score") or 0), reverse=True)
        return {
            "priorities": scored,
            "count": len(scored),
            "auto_run": False,
            "note": "IV prioritizes research only",
        }

    def seed_canonical_evidence(self, *, actor: str = "seed_import") -> dict[str, Any]:
        """Import known M1/M2/ops evidence without altering meaning."""
        # Hypothesis: IM incremental value — inconclusive at fixture n=6
        hyp = self.create_hypothesis(
            {
                "title": "IM Policy/Agents incremental value vs RAW/TMX Native",
                "description": (
                    "Whether IM Policy 1.0.0 and M2 agent-augmented shadow add incremental "
                    "economic value prospectively. Fixture retrospective n=6 is insufficient."
                ),
                "status": "INCONCLUSIVE",
                "claim_type": "INCREMENTAL_VALUE",
                "falsification_criteria": [
                    "trusted prospective n>=20 with no incremental value after costs",
                ],
                "failure_criteria": ["INSUFFICIENT_SAMPLE"],
                "source": "M2_RETROSPECTIVE_REPLAY",
                "created_from_agent": False,
            },
            actor=actor,
        )
        seeds = [
            {
                "hypothesis_id": hyp["hypothesis_id"],
                "evidence_type": "RETROSPECTIVE_DIAGNOSTIC",
                "direction": "NEUTRAL",
                "source_system": "TradingMaxxxing",
                "source_artifact": "docs/reviews/TMX_IM_RETROSPECTIVE_AGENT_REPLAY_V1_REPORT.md",
                "summary": "NO_AGENT_INCREMENTAL_VALUE at fixture n=6 — INCONCLUSIVE / INSUFFICIENT_SAMPLE",
                "n_raw": 6,
                "n_unique": 6,
                "n_trusted": 0,
                "n_effective": 6,
                "limitations": ["FIXTURE_CONTROLLED", "INSUFFICIENT_SAMPLE", "POST_HOC_DIAGNOSTIC"],
                "retrospective_or_prospective": "RETROSPECTIVE",
                "fixture_or_canary": True,
            },
            {
                "hypothesis_id": hyp["hypothesis_id"],
                "evidence_type": "POLICY_EVALUATION",
                "direction": "NEUTRAL",
                "source_system": "IntelligenceMaxxxing",
                "source_artifact": "IM_TRADING_DECISION_POLICY@1.0.0",
                "summary": "Policy 1.0.0 frozen; mostly abstaining prospectively",
                "limitations": ["NO_TRUSTED_BASE_RATE", "POLICY_FROZEN"],
                "retrospective_or_prospective": "PROSPECTIVE",
            },
            {
                "hypothesis_id": hyp["hypothesis_id"],
                "evidence_type": "OPERATIONAL_HEALTH",
                "direction": "DATA_QUALITY",
                "source_system": "TradingMaxxxing",
                "source_artifact": "tmx_im_bridge_v1/ops_24h_audit_v1",
                "summary": "24H audit: PROCESS_ALIVE_PIPELINE_STALLED; TERMINAL_UNAVAILABLE; no real prospective setups",
                "limitations": ["OPERATIONAL_NOT_ECONOMIC"],
                "retrospective_or_prospective": "PROSPECTIVE",
            },
        ]
        created = [self.create_evidence(s, actor=actor) for s in seeds]
        learning = self.create_learning(
            {
                "source_hypothesis": hyp["hypothesis_id"],
                "source_evidence": created[0]["evidence_id"],
                "what_was_believed_before": "Agents might add incremental value",
                "what_was_observed": "Fixture n=6 showed no incremental value; sample insufficient",
                "what_changed": "Status set INCONCLUSIVE pending prospective n>=20",
                "what_did_not_change": "Policy 1.0.0 frozen; no promotion",
                "confidence_before": 0.3,
                "confidence_after": 0.2,
                "contradictions": [],
                "open_questions": ["Does prospective FORWARD sample change the conclusion?"],
                "decision_taken": "KEEP_POLICY_1_0_0_FROZEN",
                "decision_not_taken": "NO_LIVE_PROMOTION",
                "policy_implication": "NONE",
            },
            actor=actor,
        )
        # Pre-register placeholder experiment awaiting manual approval (not running).
        exp = self.create_experiment(
            {
                "hypothesis_id": hyp["hypothesis_id"],
                "title": "Prospective observation gate for IM incremental value",
                "mode": "PROSPECTIVE_SHADOW",
                "status": "PRE_REGISTERED",
                "dataset_origins": ["FORWARD"],
                "success_criteria": ["trusted_closed_setups>=20"],
                "failure_criteria": ["INSUFFICIENT_SAMPLE"],
                "limitations": ["NO_AUTO_RUN", "NO_OOS", "NO_POLICY_MUTATION"],
            },
            actor=actor,
        )
        return {
            "hypothesis": hyp,
            "evidence": created,
            "learning": learning,
            "experiment": exp,
            "seeded": True,
        }
