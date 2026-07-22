"""ReportAgentV1 — structured reports only; no Ollama; never invents zeros or edge claims."""

from __future__ import annotations

from typing import Any

from intelligence_maxxxing.domain_packs.research_factory_m3a.hashes import content_hash, new_id, utc_now
from intelligence_maxxxing.domain_packs.research_factory_m3b.constants import (
    ECONOMIC_VERDICTS,
    FORBIDDEN_ECONOMIC_VERDICTS,
    M3B_ID,
    M3B_VERSION,
    REPORT_TYPES,
    STRUCTURED_REPORT_SCHEMA,
)

AGENT_ID = "ReportAgentV1"
AGENT_VERSION = "1.0.0"

_NA = "N/A"


def _na_or(value: Any) -> Any:
    if value is None:
        return _NA
    return value


def _sample_counts(artifacts: dict[str, Any]) -> dict[str, Any]:
    """Preserve N/A; never coerce missing to 0."""
    samples = artifacts.get("sample_counts") if isinstance(artifacts.get("sample_counts"), dict) else {}
    keys = ("n_raw", "n_unique", "n_trusted", "n_effective")
    out: dict[str, Any] = {}
    for key in keys:
        if key in artifacts and artifacts[key] is not None:
            out[key] = artifacts[key]
        elif key in samples and samples[key] is not None:
            out[key] = samples[key]
        else:
            out[key] = _NA
    return out


def _economic_verdict(artifacts: dict[str, Any], counts: dict[str, Any]) -> str:
    requested = str(artifacts.get("economic_verdict") or "").upper()
    if requested in FORBIDDEN_ECONOMIC_VERDICTS:
        raise ValueError(f"forbidden economic verdict: {requested}")
    if requested in ECONOMIC_VERDICTS:
        return requested

    if artifacts.get("data_quality_blocked"):
        return "DATA_QUALITY_BLOCKED"

    n_trusted = counts.get("n_trusted")
    n_effective = counts.get("n_effective")
    if n_trusted is None or n_trusted == _NA:
        return "INSUFFICIENT_SAMPLE"
    try:
        nt = int(n_trusted)
    except (TypeError, ValueError):
        return "INSUFFICIENT_SAMPLE"
    if nt < 30:
        return "INSUFFICIENT_SAMPLE"

    if n_effective is None or n_effective == _NA:
        return "INSUFFICIENT_SAMPLE"

    incremental = artifacts.get("incremental_value")
    if incremental is None or incremental == _NA:
        return "NO_INCREMENTAL_VALUE"
    try:
        iv = float(incremental)
    except (TypeError, ValueError):
        return "NO_INCREMENTAL_VALUE"
    if iv <= 0:
        return "NO_INCREMENTAL_VALUE"
    if nt < 100:
        return "PRELIMINARY_INCREMENTAL_VALUE"
    return "ROBUST_INCREMENTAL_VALUE_NOT_YET_PROVEN"


class ReportAgentV1:
    agent_id = AGENT_ID
    agent_version = AGENT_VERSION

    def generate(self, report_type: str, artifacts: dict[str, Any]) -> dict[str, Any]:
        rtype = str(report_type or "").upper()
        if rtype not in REPORT_TYPES:
            raise ValueError(f"invalid report_type: {report_type}")
        if not isinstance(artifacts, dict):
            raise ValueError("artifacts must be a dict")

        # Refuse forbidden claims if smuggled in.
        for key in ("economic_verdict", "verdict", "claim"):
            val = str(artifacts.get(key) or "").upper()
            if val in FORBIDDEN_ECONOMIC_VERDICTS:
                raise ValueError(f"forbidden claim '{val}' not allowed in structured reports")

        counts = _sample_counts(artifacts)
        gross = _na_or(artifacts.get("gross_R") if "gross_R" in artifacts else artifacts.get("gross"))
        trusted = _na_or(
            artifacts.get("trusted_net_R")
            if "trusted_net_R" in artifacts
            else artifacts.get("trusted")
        )

        sections: list[dict[str, Any]] = []
        economic_verdict: str | None = None

        if rtype == "EVIDENCE_BUNDLE_SUMMARY":
            bundle = artifacts.get("evidence_bundle") or artifacts
            sections.append(
                {
                    "section_id": "trust",
                    "title": "Trust status",
                    "fields": {
                        "trust_status": _na_or(bundle.get("trust_status")),
                        "temporal_label": _na_or(bundle.get("temporal_label")),
                        "origin_label": _na_or(bundle.get("origin_label")),
                        "n_items": _na_or((bundle.get("coverage") or {}).get("n_items")),
                    },
                }
            )
        elif rtype == "SAFETY_AUDIT_SUMMARY":
            audit = artifacts.get("safety_audit") or artifacts
            sections.append(
                {
                    "section_id": "overall",
                    "title": "Safety overall",
                    "fields": {
                        "overall_status": _na_or(audit.get("overall_status")),
                        "critical_failures": list(audit.get("critical_failures") or []),
                        "informs_only": True,
                    },
                }
            )
        elif rtype == "ECONOMIC_INCREMENTAL_VALUE":
            economic_verdict = _economic_verdict(artifacts, counts)
            sections.append(
                {
                    "section_id": "economy",
                    "title": "Economic incremental value",
                    "fields": {
                        "gross": gross,
                        "trusted": trusted,
                        "n_raw": counts["n_raw"],
                        "n_unique": counts["n_unique"],
                        "n_trusted": counts["n_trusted"],
                        "n_effective": counts["n_effective"],
                        "economic_verdict": economic_verdict,
                        "note": "gross and trusted kept separate; missing never filled with 0",
                    },
                }
            )
        elif rtype == "DAILY_RESEARCH_STATUS":
            sections.append(
                {
                    "section_id": "daily",
                    "title": "Daily research status",
                    "fields": {
                        "status": _na_or(artifacts.get("status")),
                        "n_raw": counts["n_raw"],
                        "n_trusted": counts["n_trusted"],
                        "milestone_3_complete": False,
                        "auto_run": False,
                    },
                }
            )
        elif rtype == "EXPERIMENT_READINESS":
            sections.append(
                {
                    "section_id": "readiness",
                    "title": "Experiment readiness",
                    "fields": {
                        "ready": False,
                        "manual_approval_required": True,
                        "auto_run": False,
                        "reason": _na_or(artifacts.get("reason") or "M3B_FOUNDATION_ONLY"),
                    },
                }
            )
        elif rtype == "REGISTRY_QUALITY":
            sections.append(
                {
                    "section_id": "registry",
                    "title": "Registry quality",
                    "fields": {
                        "append_only": _na_or(artifacts.get("append_only")),
                        "manual_approval": _na_or(artifacts.get("manual_approval")),
                        "auto_run": False,
                        "notes": _na_or(artifacts.get("notes")),
                    },
                }
            )

        input_hash = content_hash(
            {
                "report_type": rtype,
                "artifact_keys": sorted(artifacts.keys()),
                "counts": counts,
                "gross": gross,
                "trusted": trusted,
                "refs": {
                    "bundle_id": (artifacts.get("evidence_bundle") or {}).get("bundle_id")
                    if isinstance(artifacts.get("evidence_bundle"), dict)
                    else artifacts.get("bundle_id"),
                    "audit_id": (artifacts.get("safety_audit") or {}).get("audit_id")
                    if isinstance(artifacts.get("safety_audit"), dict)
                    else artifacts.get("audit_id"),
                },
            }
        )

        body: dict[str, Any] = {
            "schema_version": STRUCTURED_REPORT_SCHEMA,
            "report_id": new_id("RPT"),
            "report_type": rtype,
            "m3b_id": M3B_ID,
            "m3b_version": M3B_VERSION,
            "agent_id": AGENT_ID,
            "agent_version": AGENT_VERSION,
            "created_at": utc_now(),
            "sections": sections,
            "sample_counts": counts,
            "gross": gross,
            "trusted": trusted,
            "economic_verdict": economic_verdict,
            "forbidden_claims_blocked": sorted(FORBIDDEN_ECONOMIC_VERDICTS),
            "ollama_used": False,
            "non_authoritative": True,
            "append_only": True,
            "research_only": True,
            "live_control": False,
            "promotion_eligible": False,
            "limitations": [
                "STRUCTURED_ONLY",
                "NO_OLLAMA",
                "N_A_PRESERVED",
                "GROSS_TRUSTED_SEPARATED",
                "NO_EDGE_CONFIRMED_CLAIMS",
            ],
            "input_hash": input_hash,
        }
        stable = {
            k: v
            for k, v in body.items()
            if k not in {"report_id", "created_at", "output_hash", "content_hash"}
        }
        body["content_hash"] = content_hash(stable)
        body["output_hash"] = body["content_hash"]
        return body
