"""IM-side checks for family contextual adjudication docs (Policy/M2 unchanged)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_adjudication_docs_exist():
    review = ROOT / "docs/reviews/TRADING_FAMILY_CONTEXTUAL_POLICY_ADJUDICATION_V1.md"
    runbook = ROOT / "docs/runbooks/LOCAL_FAMILY_CANDIDATE_ADJUDICATION_V1.md"
    assert review.is_file()
    assert runbook.is_file()
    text = review.read_text(encoding="utf-8")
    assert "FAMILY_EDGE_ADJUDICATION_COMPLETE_VALID_NEAR_MISS" in text
    assert "1.0.0" in text
    assert "unchanged" in text.lower()


def test_policy_files_untouched_markers():
    # Smoke: policy module still importable / present; adjudication did not delete it.
    policy = ROOT / "src/intelligence_maxxxing/domain_packs/trading/policy_v1.py"
    assert policy.is_file()
