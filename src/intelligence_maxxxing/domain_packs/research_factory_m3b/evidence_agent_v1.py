"""EvidenceAgentV1 — deterministic, read-only evidence bundling; never invents evidence."""

from __future__ import annotations

from typing import Any

from intelligence_maxxxing.domain_packs.research_factory_m3a.hashes import content_hash, new_id, utc_now
from intelligence_maxxxing.domain_packs.research_factory_m3b.constants import (
    EVIDENCE_BUNDLE_SCHEMA,
    M3B_ID,
    M3B_VERSION,
)
from intelligence_maxxxing.domain_packs.trading.agents._common import has_forbidden_outcome_fields

AGENT_ID = "EvidenceAgentV1"
AGENT_VERSION = "1.0.0"


class EvidenceAgentError(ValueError):
    """Raised when subject violates pre-outcome / invent-evidence rules."""


def _ref_id(prefix: str, obj: dict[str, Any] | None, *keys: str) -> str | None:
    if not isinstance(obj, dict):
        return None
    for key in keys:
        val = obj.get(key)
        if val:
            return f"{prefix}:{val}"
    return None


def _is_fixture(obj: dict[str, Any] | None) -> bool:
    if not isinstance(obj, dict):
        return False
    if obj.get("fixture_or_canary") or obj.get("is_fixture"):
        return True
    origin = str(obj.get("origin") or obj.get("dataset_origin") or "").upper()
    return origin in {"FIXTURE", "CANARY", "SYNTHETIC"}


def _temporal_label(subject: dict[str, Any]) -> str:
    mode = str(subject.get("experiment_mode") or "").upper()
    if mode in {"PROSPECTIVE", "FORWARD", "LIVE_PAPER"}:
        return "PROSPECTIVE"
    if mode in {"RETROSPECTIVE", "RETROSPECTIVE_DIAGNOSTIC", "REPLAY"}:
        return "RETROSPECTIVE"
    for key in ("observation", "assessment", "context", "anomaly", "critic", "shadow"):
        obj = subject.get(key)
        if isinstance(obj, dict):
            label = str(
                obj.get("retrospective_or_prospective")
                or obj.get("temporal_validity")
                or obj.get("experiment_mode")
                or ""
            ).upper()
            if "PROSPECTIVE" in label or label in {"FORWARD", "LIVE_PAPER"}:
                return "PROSPECTIVE"
            if "RETROSPECTIVE" in label or label == "REPLAY":
                return "RETROSPECTIVE"
    return "UNSPECIFIED"


def _outcome_available_at(outcome: dict[str, Any]) -> str:
    return str(
        outcome.get("available_at")
        or outcome.get("resolved_at")
        or outcome.get("exit_time")
        or outcome.get("observed_at_utc")
        or ""
    )


def _classify_from_registry(entry: dict[str, Any]) -> str:
    direction = str(entry.get("direction") or "NEUTRAL").upper()
    if direction in {"SUPPORTING", "CONTRADICTING", "NEUTRAL", "DATA_QUALITY"}:
        return direction
    return "NEUTRAL"


class EvidenceAgentV1:
    agent_id = AGENT_ID
    agent_version = AGENT_VERSION

    def build_bundle(self, subject: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(subject, dict):
            raise EvidenceAgentError("subject must be a dict")

        cutoff = str(subject.get("cutoff_utc") or "")
        observation = subject.get("observation") if isinstance(subject.get("observation"), dict) else None
        assessment = subject.get("assessment") if isinstance(subject.get("assessment"), dict) else None
        context = subject.get("context") if isinstance(subject.get("context"), dict) else None
        anomaly = subject.get("anomaly") if isinstance(subject.get("anomaly"), dict) else None
        critic = subject.get("critic") if isinstance(subject.get("critic"), dict) else None
        shadow = subject.get("shadow") if isinstance(subject.get("shadow"), dict) else None
        outcome_ref = subject.get("outcome_ref") if isinstance(subject.get("outcome_ref"), dict) else None
        cost = subject.get("cost") if isinstance(subject.get("cost"), dict) else None
        registry_evidence = subject.get("registry_evidence") if isinstance(subject.get("registry_evidence"), list) else []
        reports = subject.get("reports") if isinstance(subject.get("reports"), list) else []

        # Pre-outcome surfaces must not carry forbidden outcome fields.
        pre_outcome_surfaces = {
            "observation": observation,
            "assessment": assessment,
            "context": context,
            "anomaly": anomaly,
            "critic": critic,
            "shadow": shadow,
            "cost": cost,
        }
        leak_hits: list[str] = []
        for name, obj in pre_outcome_surfaces.items():
            if obj is None:
                continue
            hits = has_forbidden_outcome_fields(obj)
            leak_hits.extend(f"{name}.{h}" for h in hits)
        if leak_hits:
            raise EvidenceAgentError(
                f"forbidden outcome fields in pre-outcome surfaces: {sorted(leak_hits)}"
            )

        items: list[dict[str, Any]] = []
        limitations: list[str] = [
            "DETERMINISTIC_V1",
            "NON_AUTHORITATIVE",
            "NO_INVENTED_EVIDENCE",
        ]
        missing: list[str] = []

        def add_item(
            *,
            source_kind: str,
            source_ref: str | None,
            direction: str,
            summary: str,
            strength: str = "WEAK",
            labels: dict[str, Any] | None = None,
        ) -> None:
            if not source_ref:
                return
            items.append(
                {
                    "item_id": f"EBI_{content_hash({'ref': source_ref, 'dir': direction, 'sum': summary})[:16]}",
                    "source_kind": source_kind,
                    "source_ref": source_ref,
                    "direction": direction,
                    "summary": summary,
                    "strength": strength,
                    "labels": labels or {},
                }
            )

        if observation is None:
            missing.append("observation")
        else:
            add_item(
                source_kind="observation",
                source_ref=_ref_id("observation", observation, "observation_id", "id"),
                direction="NEUTRAL",
                summary="observation_ref_present",
                labels={"provided": True},
            )

        if assessment is None:
            missing.append("assessment")
        else:
            decision = str(assessment.get("decision") or "UNKNOWN")
            add_item(
                source_kind="assessment",
                source_ref=_ref_id("assessment", assessment, "assessment_id", "id"),
                direction="NEUTRAL",
                summary=f"policy_decision={decision}",
                labels={"decision": decision},
            )

        if context is not None:
            health = str(context.get("market_data_health") or "")
            direction = "DATA_QUALITY" if health in {"DEGRADED", "FAILED", "STALE"} else "SUPPORTING"
            if health in {"", "UNKNOWN"}:
                direction = "NEUTRAL"
            add_item(
                source_kind="context",
                source_ref=_ref_id("context", context, "context_assessment_id", "id"),
                direction=direction,
                summary=f"market_data_health={health or 'N/A'}",
                labels={"market_data_health": health or "N/A"},
            )
        else:
            missing.append("context")

        if anomaly is not None:
            findings = anomaly.get("findings") if isinstance(anomaly.get("findings"), list) else None
            if findings is None and anomaly.get("anomaly_type"):
                findings = [anomaly]
            findings = findings or []
            critical = [
                f
                for f in findings
                if isinstance(f, dict)
                and str(f.get("severity")) == "CRITICAL"
                and str(f.get("anomaly_type") or "") != "NO_ANOMALY"
            ]
            if critical:
                for f in critical:
                    add_item(
                        source_kind="anomaly",
                        source_ref=_ref_id("anomaly", f, "finding_id", "anomaly_finding_id", "id")
                        or _ref_id("anomaly", anomaly, "finding_id", "id"),
                        direction="CONTRADICTING",
                        summary=f"critical_anomaly={f.get('anomaly_type')}",
                        strength="STRONG",
                        labels={"severity": "CRITICAL", "anomaly_type": f.get("anomaly_type")},
                    )
            elif findings:
                add_item(
                    source_kind="anomaly",
                    source_ref=_ref_id("anomaly", findings[0] if isinstance(findings[0], dict) else anomaly, "finding_id", "id")
                    or _ref_id("anomaly", anomaly, "finding_id", "id"),
                    direction="NEUTRAL",
                    summary="anomaly_findings_non_critical",
                )
            else:
                add_item(
                    source_kind="anomaly",
                    source_ref=_ref_id("anomaly", anomaly, "finding_id", "id"),
                    direction="NEUTRAL",
                    summary="anomaly_ref_present_no_findings",
                )
        else:
            missing.append("anomaly")

        if critic is not None:
            objections = critic.get("objections") or critic.get("contradicting") or []
            supporting = critic.get("supporting") or []
            dq = critic.get("data_quality_objections") or []
            if dq:
                add_item(
                    source_kind="critic",
                    source_ref=_ref_id("critic", critic, "critic_review_id", "id"),
                    direction="DATA_QUALITY",
                    summary=f"critic_dq={len(dq)}",
                    strength="STRONG",
                    labels={"dq_count": len(dq)},
                )
            if objections:
                add_item(
                    source_kind="critic",
                    source_ref=_ref_id("critic", critic, "critic_review_id", "id"),
                    direction="CONTRADICTING",
                    summary=f"critic_objections={len(objections)}",
                    strength="STRONG",
                    labels={"objection_count": len(objections)},
                )
            elif supporting:
                add_item(
                    source_kind="critic",
                    source_ref=_ref_id("critic", critic, "critic_review_id", "id"),
                    direction="SUPPORTING",
                    summary=f"critic_supporting={len(supporting)}",
                    labels={"supporting_count": len(supporting)},
                )
            else:
                add_item(
                    source_kind="critic",
                    source_ref=_ref_id("critic", critic, "critic_review_id", "id"),
                    direction="NEUTRAL",
                    summary="critic_ref_present",
                )
        else:
            missing.append("critic")

        if shadow is not None:
            status = str(shadow.get("status") or "")
            if status == "DOWNGRADE":
                direction = "CONTRADICTING"
            elif status == "UPHOLD":
                direction = "SUPPORTING"
            else:
                direction = "NEUTRAL"
            add_item(
                source_kind="shadow",
                source_ref=_ref_id("shadow", shadow, "shadow_adjudication_id", "id"),
                direction=direction,
                summary=f"shadow_status={status or 'N/A'}",
                labels={"status": status or "N/A"},
            )
        else:
            missing.append("shadow")

        if cost is not None:
            coverage = cost.get("cost_coverage")
            if coverage in {None, "N/A", ""}:
                add_item(
                    source_kind="cost",
                    source_ref=_ref_id("cost", cost, "cost_id", "id") or "cost:provided",
                    direction="DATA_QUALITY",
                    summary="cost_coverage=N/A",
                    labels={"cost_coverage": "N/A"},
                )
            elif float(coverage or 0) < 1.0:
                add_item(
                    source_kind="cost",
                    source_ref=_ref_id("cost", cost, "cost_id", "id") or "cost:provided",
                    direction="DATA_QUALITY",
                    summary=f"cost_coverage={coverage}",
                    labels={"cost_coverage": coverage},
                )
            else:
                add_item(
                    source_kind="cost",
                    source_ref=_ref_id("cost", cost, "cost_id", "id") or "cost:provided",
                    direction="SUPPORTING",
                    summary=f"cost_coverage={coverage}",
                    labels={"cost_coverage": coverage},
                )

        for entry in registry_evidence:
            if not isinstance(entry, dict):
                continue
            add_item(
                source_kind="registry_evidence",
                source_ref=_ref_id("evidence", entry, "evidence_id", "id")
                or f"registry:{content_hash(entry)[:12]}",
                direction=_classify_from_registry(entry),
                summary=str(entry.get("summary") or "registry_evidence"),
                labels={
                    "fixture_or_canary": bool(entry.get("fixture_or_canary")),
                    "retrospective_or_prospective": entry.get("retrospective_or_prospective")
                    or "UNSPECIFIED",
                },
            )

        for report in reports:
            if not isinstance(report, dict):
                continue
            add_item(
                source_kind="report",
                source_ref=_ref_id("report", report, "report_id", "id")
                or f"report:{content_hash(report)[:12]}",
                direction="NEUTRAL",
                summary=str(report.get("title") or report.get("summary") or "report_ref"),
                labels={"report_type": report.get("report_type") or "N/A"},
            )

        # Outcome handling: only after cutoff, and only as PENDING_OUTCOME labeled items.
        if outcome_ref is not None:
            available = _outcome_available_at(outcome_ref)
            if not cutoff:
                raise EvidenceAgentError("outcome_ref requires cutoff_utc for temporal gate")
            if available and available <= cutoff:
                raise EvidenceAgentError(
                    f"outcome available_at ({available}) must be after cutoff_utc ({cutoff})"
                )
            # Outcome present but post-cutoff: label PENDING_OUTCOME (not decision evidence).
            add_item(
                source_kind="outcome_ref",
                source_ref=_ref_id("outcome", outcome_ref, "outcome_id", "id") or "outcome:ref",
                direction="PENDING_OUTCOME",
                summary="outcome_after_cutoff_pending_label_only",
                labels={
                    "available_at": available or "N/A",
                    "cutoff_utc": cutoff,
                    "not_for_pre_outcome_decision": True,
                },
            )
            limitations.append("OUTCOME_LABELED_PENDING_ONLY")

        directions = {str(i.get("direction")) for i in items}
        has_support = "SUPPORTING" in directions
        has_contra = "CONTRADICTING" in directions
        has_dq = "DATA_QUALITY" in directions
        has_pending = "PENDING_OUTCOME" in directions

        fixture_flags = [
            _is_fixture(observation),
            _is_fixture(assessment),
            _is_fixture(context),
            any(
                isinstance(e, dict) and bool(e.get("fixture_or_canary"))
                for e in registry_evidence
            ),
        ]
        any_fixture = any(fixture_flags)
        any_real = any(
            isinstance(obj, dict) and not _is_fixture(obj)
            for obj in (observation, assessment, context, anomaly, critic, shadow)
            if obj is not None
        ) or any(
            isinstance(e, dict) and not e.get("fixture_or_canary") for e in registry_evidence
        )

        if has_dq and not has_support and not has_contra:
            trust_status = "DATA_QUALITY_BLOCKED"
        elif has_support and has_contra:
            trust_status = "CONFLICTED"
        elif not items or (missing and not items):
            trust_status = "MISSING_EVIDENCE"
        elif has_pending and not has_support and not has_contra:
            trust_status = "PENDING_OUTCOME"
        elif any_fixture and not any_real:
            trust_status = "FIXTURE_ONLY"
        elif has_support and not has_contra:
            trust_status = "TRUSTED" if not any_fixture else "PARTIAL"
        elif has_contra and not has_support:
            trust_status = "UNTRUSTED"
        elif missing:
            trust_status = "PARTIAL"
        else:
            trust_status = "PARTIAL"

        if not items:
            trust_status = "MISSING_EVIDENCE"
            limitations.append("NO_EVIDENCE_ITEMS")

        temporal = _temporal_label(subject)
        if any_fixture and any_real:
            origin_label = "MIXED"
        elif any_fixture:
            origin_label = "FIXTURE"
        elif any_real:
            origin_label = "REAL"
        else:
            origin_label = "UNKNOWN"

        coverage = {
            "provided_kinds": sorted({str(i.get("source_kind")) for i in items}),
            "missing_kinds": sorted(set(missing)),
            "n_items": len(items),
            "n_supporting": sum(1 for i in items if i.get("direction") == "SUPPORTING"),
            "n_contradicting": sum(1 for i in items if i.get("direction") == "CONTRADICTING"),
            "n_neutral": sum(1 for i in items if i.get("direction") == "NEUTRAL"),
            "n_data_quality": sum(1 for i in items if i.get("direction") == "DATA_QUALITY"),
            "n_pending_outcome": sum(1 for i in items if i.get("direction") == "PENDING_OUTCOME"),
        }

        subject_refs = {
            "observation_id": (observation or {}).get("observation_id"),
            "assessment_id": (assessment or {}).get("assessment_id"),
            "context_assessment_id": (context or {}).get("context_assessment_id"),
            "critic_review_id": (critic or {}).get("critic_review_id"),
            "shadow_adjudication_id": (shadow or {}).get("shadow_adjudication_id"),
            "outcome_id": (outcome_ref or {}).get("outcome_id") if outcome_ref else None,
            "experiment_mode": subject.get("experiment_mode"),
            "cutoff_utc": cutoff or None,
        }

        input_hash = content_hash(
            {
                "subject_refs": subject_refs,
                "registry_ids": [
                    e.get("evidence_id") for e in registry_evidence if isinstance(e, dict)
                ],
                "report_ids": [r.get("report_id") for r in reports if isinstance(r, dict)],
                "cutoff_utc": cutoff,
                "experiment_mode": subject.get("experiment_mode"),
            }
        )

        body: dict[str, Any] = {
            "schema_version": EVIDENCE_BUNDLE_SCHEMA,
            "bundle_id": new_id("EB"),
            "m3b_id": M3B_ID,
            "m3b_version": M3B_VERSION,
            "agent_id": AGENT_ID,
            "agent_version": AGENT_VERSION,
            "created_at": utc_now(),
            "subject_refs": subject_refs,
            "items": items,
            "trust_status": trust_status,
            "temporal_label": temporal,
            "origin_label": origin_label,
            "coverage": coverage,
            "limitations": limitations,
            "input_hash": input_hash,
            "non_authoritative": True,
            "append_only": True,
            "research_only": True,
            "live_control": False,
            "promotion_eligible": False,
            "mutates_live_policy": False,
        }
        stable = {
            k: v
            for k, v in body.items()
            if k not in {"bundle_id", "created_at", "output_hash", "content_hash"}
        }
        body["content_hash"] = content_hash(stable)
        body["output_hash"] = body["content_hash"]
        return body
