"""M3B Evidence / Safety / Report foundation unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from intelligence_maxxxing.domain_packs.research_factory_m3b.evidence_agent_v1 import (
    EvidenceAgentError,
    EvidenceAgentV1,
)
from intelligence_maxxxing.domain_packs.research_factory_m3b.report_agent_v1 import ReportAgentV1
from intelligence_maxxxing.domain_packs.research_factory_m3b.safety_auditor_agent_v1 import (
    SafetyAuditorAgentV1,
)
from intelligence_maxxxing.domain_packs.research_factory_m3b.service_v1 import ResearchM3BService
from intelligence_maxxxing.domain_packs.research_factory_m3b.store_v1 import ResearchM3BStore


def _healthy_probes(**overrides: object) -> dict:
    base = {
        "broker_calls": 0,
        "tmx_storage_access": False,
        "ollama_invoked": False,
        "oos_rows_read": 0,
        "future_feature_count": 0,
        "outcome_leakage_count": 0,
        "auto_run": False,
        "auto_promotion": False,
        "manual_approval_required": True,
        "milestone_3_complete": False,
        "gross_trusted_separated": True,
        "execution_enabled": False,
        "policy_mutations": 0,
        "policy_frozen": True,
        "bundle_frozen": True,
    }
    base.update(overrides)
    return base


def test_evidence_supporting_and_contradicting() -> None:
    agent = EvidenceAgentV1()
    bundle = agent.build_bundle(
        {
            "experiment_mode": "PROSPECTIVE",
            "observation": {"observation_id": "obs1", "origin": "FORWARD"},
            "assessment": {"assessment_id": "a1", "decision": "TAKE"},
            "context": {
                "context_assessment_id": "c1",
                "market_data_health": "OK",
            },
            "critic": {
                "critic_review_id": "cr1",
                "objections": ["SPREAD_OBJECTION"],
                "supporting": [],
            },
            "shadow": {"shadow_adjudication_id": "sh1", "status": "DOWNGRADE"},
        }
    )
    dirs = {i["direction"] for i in bundle["items"]}
    assert "CONTRADICTING" in dirs
    assert bundle["trust_status"] == "CONFLICTED" or "CONTRADICTING" in dirs
    assert bundle["non_authoritative"] is True
    assert bundle["append_only"] is True
    assert bundle["temporal_label"] == "PROSPECTIVE"


def test_evidence_supporting_only() -> None:
    agent = EvidenceAgentV1()
    bundle = agent.build_bundle(
        {
            "experiment_mode": "PROSPECTIVE",
            "observation": {"observation_id": "obs2", "origin": "FORWARD"},
            "assessment": {"assessment_id": "a2", "decision": "TAKE"},
            "context": {"context_assessment_id": "c2", "market_data_health": "OK"},
            "critic": {"critic_review_id": "cr2", "supporting": ["OK"], "objections": []},
            "shadow": {"shadow_adjudication_id": "sh2", "status": "UPHOLD"},
        }
    )
    assert bundle["coverage"]["n_supporting"] >= 1
    assert bundle["coverage"]["n_contradicting"] == 0
    assert bundle["trust_status"] in {"TRUSTED", "PARTIAL"}


def test_evidence_missing() -> None:
    agent = EvidenceAgentV1()
    bundle = agent.build_bundle({})
    assert bundle["trust_status"] == "MISSING_EVIDENCE"
    assert bundle["coverage"]["n_items"] == 0


def test_evidence_conflicted() -> None:
    agent = EvidenceAgentV1()
    bundle = agent.build_bundle(
        {
            "registry_evidence": [
                {"evidence_id": "e1", "direction": "SUPPORTING", "summary": "for"},
                {"evidence_id": "e2", "direction": "CONTRADICTING", "summary": "against"},
            ]
        }
    )
    assert bundle["trust_status"] == "CONFLICTED"


def test_evidence_no_invented() -> None:
    agent = EvidenceAgentV1()
    bundle = agent.build_bundle(
        {"observation": {"observation_id": "only_obs", "origin": "FORWARD"}}
    )
    kinds = {i["source_kind"] for i in bundle["items"]}
    assert kinds == {"observation"}
    assert all(i.get("source_ref") for i in bundle["items"])


def test_evidence_no_outcome_before_cutoff() -> None:
    agent = EvidenceAgentV1()
    with pytest.raises(EvidenceAgentError):
        agent.build_bundle(
            {
                "observation": {"observation_id": "o", "realized_R": 1.2},
                "cutoff_utc": "2026-07-01T00:00:00Z",
            }
        )
    with pytest.raises(EvidenceAgentError):
        agent.build_bundle(
            {
                "cutoff_utc": "2026-07-01T12:00:00Z",
                "outcome_ref": {
                    "outcome_id": "out1",
                    "available_at": "2026-07-01T11:00:00Z",
                    "realized_R": 0.5,
                },
            }
        )


def test_evidence_outcome_after_cutoff_pending_only() -> None:
    agent = EvidenceAgentV1()
    bundle = agent.build_bundle(
        {
            "cutoff_utc": "2026-07-01T12:00:00Z",
            "observation": {"observation_id": "o2"},
            "outcome_ref": {
                "outcome_id": "out2",
                "available_at": "2026-07-01T13:00:00Z",
                "realized_R": 0.5,
            },
        }
    )
    pending = [i for i in bundle["items"] if i["direction"] == "PENDING_OUTCOME"]
    assert len(pending) == 1
    assert pending[0]["labels"]["not_for_pre_outcome_decision"] is True


def test_safety_oos_broker_execution_policy_future_leakage() -> None:
    agent = SafetyAuditorAgentV1()
    cases = [
        ("oos_rows_read", 3, "OOS_ROWS_READ"),
        ("broker_calls", 1, "BROKER_CALLS_DETECTED"),
        ("execution_enabled", True, "EXECUTION_ENABLED"),
        ("policy_mutations", 2, "POLICY_MUTATION_DETECTED"),
        ("future_feature_count", 1, "FUTURE_FEATURES_DETECTED"),
        ("outcome_leakage_count", 1, "OUTCOME_LEAKAGE"),
    ]
    for key, value, code in cases:
        audit = agent.audit(_healthy_probes(**{key: value}))
        assert audit["overall_status"] == "SAFETY_BLOCKED"
        assert code in audit["critical_failures"]
        assert audit["informs_only"] is True
        assert audit["kills_process"] is False
        assert audit["mutates_config"] is False


def test_safety_unknown_never_pass() -> None:
    agent = SafetyAuditorAgentV1()
    audit = agent.audit({"scope_label": "partial_probes", "broker_calls": 0})
    statuses = {c["status"] for c in audit["checks"]}
    assert "UNKNOWN" in statuses
    assert audit["overall_status"] in {"SAFETY_BLOCKED", "SAFETY_PARTIAL"}
    assert audit["overall_status"] != "SAFETY_PASS"
    # No UNKNOWN check may be recorded as PASS
    for c in audit["checks"]:
        if "not provided" in c["detail"]:
            assert c["status"] == "UNKNOWN"


def test_safety_healthy_pass() -> None:
    agent = SafetyAuditorAgentV1()
    audit = agent.audit(_healthy_probes())
    assert audit["overall_status"] == "SAFETY_PASS"
    assert audit["critical_failures"] == []
    assert all(c["status"] == "PASS" for c in audit["checks"])


def test_report_na_preserve_and_insufficient_sample() -> None:
    agent = ReportAgentV1()
    report = agent.generate(
        "ECONOMIC_INCREMENTAL_VALUE",
        {"gross_R": "N/A", "trusted_net_R": None},
    )
    assert report["gross"] == "N/A"
    assert report["trusted"] == "N/A"
    assert report["sample_counts"]["n_raw"] == "N/A"
    assert report["sample_counts"]["n_trusted"] == "N/A"
    assert report["economic_verdict"] == "INSUFFICIENT_SAMPLE"
    assert 0 not in report["sample_counts"].values()


def test_report_forbids_edge_confirmed() -> None:
    agent = ReportAgentV1()
    with pytest.raises(ValueError):
        agent.generate(
            "ECONOMIC_INCREMENTAL_VALUE",
            {"economic_verdict": "EDGE_CONFIRMED", "n_trusted": 100, "n_effective": 80},
        )


def test_report_hash_stability() -> None:
    agent = ReportAgentV1()
    arts = {"n_raw": 10, "n_unique": 8, "n_trusted": 5, "n_effective": 4, "gross_R": 1.0, "trusted_net_R": 0.2}
    r1 = agent.generate("ECONOMIC_INCREMENTAL_VALUE", arts)
    r2 = agent.generate("ECONOMIC_INCREMENTAL_VALUE", arts)
    assert r1["output_hash"] == r2["output_hash"]
    assert r1["content_hash"] == r2["content_hash"]
    assert r1["report_id"] != r2["report_id"]


def test_append_only_store_idempotency(tmp_path: Path) -> None:
    store = ResearchM3BStore(root=tmp_path / "m3b")
    svc = ResearchM3BService(store=store)
    subject = {
        "observation": {"observation_id": "idem1"},
        "registry_evidence": [
            {"evidence_id": "ev1", "direction": "SUPPORTING", "summary": "s"}
        ],
    }
    a = svc.create_evidence_bundle(subject)
    b = svc.create_evidence_bundle(subject)
    assert a["created"] is True
    assert b["created"] is False
    assert a["bundle_id"] == b["bundle_id"]
    assert a["output_hash"] == b["output_hash"]
    assert store.counts()["evidence_bundles"] == 1

    probes = _healthy_probes(scope_label="idem")
    s1 = svc.create_safety_audit(probes)
    s2 = svc.create_safety_audit(probes)
    assert s1["created"] is True
    assert s2["created"] is False
    assert store.counts()["safety_audits"] == 1

    r1 = svc.create_report(
        {"report_type": "DAILY_RESEARCH_STATUS", "artifacts": {"status": "N/A"}}
    )
    r2 = svc.create_report(
        {"report_type": "DAILY_RESEARCH_STATUS", "artifacts": {"status": "N/A"}}
    )
    assert r1["created"] is True
    assert r2["created"] is False
    assert store.counts()["structured_reports"] == 1


def test_health_flags(tmp_path: Path) -> None:
    svc = ResearchM3BService(store=ResearchM3BStore(root=tmp_path / "m3b"))
    h = svc.health()
    assert h["milestone_3_complete"] is False
    assert h["m3b"] is True
    assert h["auto_run"] is False
    assert h["policy_frozen"] is True
    assert h["bundle_frozen"] is True
