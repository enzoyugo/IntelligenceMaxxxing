"""IM docs checks for contextual family executable freeze / shadow."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_freeze_and_runbook_docs():
    review = ROOT / "docs/reviews/TRADING_CONTEXTUAL_FAMILY_EXECUTABLE_FREEZE_V1.md"
    arch = ROOT / "docs/architecture/CONTEXTUAL_FAMILY_INFERENCE_ARTIFACT_V1.md"
    runbook = ROOT / "docs/runbooks/LOCAL_CONTEXTUAL_FAMILY_SHADOW_INFERENCE_V1.md"
    assert review.is_file()
    assert arch.is_file()
    assert runbook.is_file()
    text = review.read_text(encoding="utf-8")
    assert "VALID_CONTEXTUAL_NEAR_MISS" in text
    assert "1.0.0" in text
    assert "unchanged" in text.lower()


def test_policy_still_present():
    assert (ROOT / "src/intelligence_maxxxing/domain_packs/trading/policy_v1.py").is_file()
