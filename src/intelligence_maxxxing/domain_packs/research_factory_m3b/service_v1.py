"""ResearchM3BService — wraps M3B agents + append-only store."""

from __future__ import annotations

from typing import Any

from intelligence_maxxxing.application.errors import ApplicationError
from intelligence_maxxxing.domain_packs.research_factory_m3a.hashes import utc_now
from intelligence_maxxxing.domain_packs.research_factory_m3b.constants import M3B_ID, M3B_VERSION
from intelligence_maxxxing.domain_packs.research_factory_m3b.evidence_agent_v1 import (
    EvidenceAgentError,
    EvidenceAgentV1,
)
from intelligence_maxxxing.domain_packs.research_factory_m3b.report_agent_v1 import ReportAgentV1
from intelligence_maxxxing.domain_packs.research_factory_m3b.safety_auditor_agent_v1 import (
    SafetyAuditorAgentV1,
)
from intelligence_maxxxing.domain_packs.research_factory_m3b.store_v1 import ResearchM3BStore


class ResearchM3BError(ApplicationError):
    code = "RESEARCH_M3B_ERROR"


class ResearchM3BNotFoundError(ApplicationError):
    code = "RESEARCH_M3B_NOT_FOUND"


class ResearchM3BService:
    def __init__(self, store: ResearchM3BStore | None = None) -> None:
        self.store = store or ResearchM3BStore()
        self.evidence_agent = EvidenceAgentV1()
        self.safety_agent = SafetyAuditorAgentV1()
        self.report_agent = ReportAgentV1()

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "research_factory_m3b",
            "m3b_id": M3B_ID,
            "m3b_version": M3B_VERSION,
            "m3b": True,
            "milestone_3_complete": False,
            "auto_run": False,
            "auto_promotion": False,
            "policy_frozen": True,
            "bundle_frozen": True,
            "research_only": True,
            "live_control": False,
            "storage": {"backend": "jsonl", "path": str(self.store.root), **self.store.counts()},
            "note": "M3B foundation only — Evidence/Safety/Report; Milestone 3 NOT_STARTED",
        }

    def create_evidence_bundle(self, subject: dict[str, Any]) -> dict[str, Any]:
        try:
            bundle = self.evidence_agent.build_bundle(subject)
        except EvidenceAgentError as exc:
            raise ResearchM3BError(str(exc)) from exc
        stored, created = self.store.append_evidence_bundle(bundle)
        self.store.append_audit(
            {
                "action": "CREATE_EVIDENCE_BUNDLE" if created else "IDEMPOTENT_EVIDENCE_BUNDLE",
                "bundle_id": stored.get("bundle_id"),
                "output_hash": stored.get("output_hash"),
                "created": created,
                "at": utc_now(),
            }
        )
        return {**stored, "created": created}

    def list_evidence_bundles(self, *, limit: int = 100) -> dict[str, Any]:
        rows = self.store.list_evidence_bundles(limit=limit)
        return {"evidence_bundles": rows, "count": len(rows)}

    def get_evidence_bundle(self, bundle_id: str) -> dict[str, Any]:
        row = self.store.get_evidence_bundle(bundle_id)
        if not row:
            raise ResearchM3BNotFoundError(f"evidence bundle not found: {bundle_id}")
        return row

    def create_safety_audit(self, scope_payload: dict[str, Any]) -> dict[str, Any]:
        audit = self.safety_agent.audit(scope_payload)
        stored, created = self.store.append_safety_audit(audit)
        self.store.append_audit(
            {
                "action": "CREATE_SAFETY_AUDIT" if created else "IDEMPOTENT_SAFETY_AUDIT",
                "audit_id": stored.get("audit_id"),
                "output_hash": stored.get("output_hash"),
                "created": created,
                "at": utc_now(),
            }
        )
        return {**stored, "created": created}

    def list_safety_audits(self, *, limit: int = 100) -> dict[str, Any]:
        rows = self.store.list_safety_audits(limit=limit)
        return {"safety_audits": rows, "count": len(rows)}

    def get_safety_audit(self, audit_id: str) -> dict[str, Any]:
        row = self.store.get_safety_audit(audit_id)
        if not row:
            raise ResearchM3BNotFoundError(f"safety audit not found: {audit_id}")
        return row

    def create_report(self, body: dict[str, Any]) -> dict[str, Any]:
        report_type = str(body.get("report_type") or "")
        artifacts = body.get("artifacts") if isinstance(body.get("artifacts"), dict) else body
        try:
            report = self.report_agent.generate(report_type, artifacts)
        except ValueError as exc:
            raise ResearchM3BError(str(exc)) from exc
        stored, created = self.store.append_structured_report(report)
        self.store.append_audit(
            {
                "action": "CREATE_STRUCTURED_REPORT" if created else "IDEMPOTENT_STRUCTURED_REPORT",
                "report_id": stored.get("report_id"),
                "output_hash": stored.get("output_hash"),
                "created": created,
                "at": utc_now(),
            }
        )
        return {**stored, "created": created}

    def list_reports(self, *, limit: int = 100) -> dict[str, Any]:
        rows = self.store.list_structured_reports(limit=limit)
        return {"reports": rows, "count": len(rows)}

    def get_report(self, report_id: str) -> dict[str, Any]:
        row = self.store.get_structured_report(report_id)
        if not row:
            raise ResearchM3BNotFoundError(f"report not found: {report_id}")
        return row
