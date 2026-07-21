"""M3A Research Factory Foundation unit tests."""

from __future__ import annotations

from pathlib import Path

from intelligence_maxxxing.application.use_cases.research_factory_m3a import (
    ResearchFactoryError,
    ResearchFactoryService,
)
from intelligence_maxxxing.domain_packs.research_factory_m3a.information_value_v1 import (
    score_information_value,
)
from intelligence_maxxxing.infrastructure.research_factory.jsonl_store import ResearchFactoryStore


def _svc(tmp_path: Path) -> ResearchFactoryService:
    return ResearchFactoryService(store=ResearchFactoryStore(root=tmp_path / "rf"))


def test_agent_cannot_create_ready_hypothesis(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    try:
        svc.create_hypothesis(
            {"title": "x", "status": "READY_FOR_EXPERIMENT", "created_from_agent": True},
            actor="agent",
        )
        assert False, "expected error"
    except ResearchFactoryError:
        pass


def test_manual_approval_requires_confirmation(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    exp = svc.create_experiment({"title": "e", "status": "PRE_REGISTERED", "hypothesis_id": "H1"})
    try:
        svc.manually_approve_experiment(exp["experiment_id"], actor="human", confirmation="nope")
        assert False
    except ResearchFactoryError:
        pass
    approved = svc.manually_approve_experiment(
        exp["experiment_id"], actor="operator", confirmation="I_CONFIRM_MANUAL_APPROVAL"
    )
    assert approved["status"] == "MANUALLY_APPROVED"
    assert approved["auto_run"] is False
    assert approved["version"] == 2


def test_append_only_learning_and_iv(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    hyp = svc.create_hypothesis({"title": "t", "status": "DRAFT"})
    ev = svc.create_evidence(
        {
            "hypothesis_id": hyp["hypothesis_id"],
            "direction": "NEUTRAL",
            "evidence_type": "RETROSPECTIVE_DIAGNOSTIC",
            "summary": "n=6 insufficient",
            "limitations": ["INSUFFICIENT_SAMPLE"],
        }
    )
    l1 = svc.create_learning(
        {
            "source_hypothesis": hyp["hypothesis_id"],
            "source_evidence": ev["evidence_id"],
            "what_was_observed": "insufficient",
            "decision_not_taken": "NO_PROMOTION",
        }
    )
    l2 = svc.create_learning(
        {
            "source_hypothesis": hyp["hypothesis_id"],
            "source_evidence": ev["evidence_id"],
            "what_was_observed": "still insufficient",
            "version": 2,
            "decision_not_taken": "NO_PROMOTION",
        }
    )
    assert l1["learning_id"] != l2["learning_id"]
    mem = svc.list_learning()
    assert mem["count"] == 2

    iv = score_information_value({"leakage_risk": 0.9, "data_quality_readiness": 0.1})
    assert "LEAKAGE_RISK_PENALTY" in iv["reason_codes"]
    assert iv["auto_run"] is False
    iv2 = score_information_value({"expected_profit_only": True})
    assert "EXPECTED_PROFIT_ONLY_PENALTY" in iv2["reason_codes"]


def test_seed_inconclusive_not_edge(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    out = svc.seed_canonical_evidence()
    assert out["hypothesis"]["status"] == "INCONCLUSIVE"
    assert out["experiment"]["status"] == "PRE_REGISTERED"
    assert out["experiment"]["auto_run"] is False
    assert any("INSUFFICIENT_SAMPLE" in (e.get("limitations") or []) for e in out["evidence"])


def test_cannot_create_running_experiment(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    try:
        svc.create_experiment({"title": "bad", "status": "RUNNING"})
        assert False
    except ResearchFactoryError:
        pass
