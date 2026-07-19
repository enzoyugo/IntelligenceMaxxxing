"""CONSTITUTION_MANIFEST_MATCHES: the frozen foundation has not been altered."""

from intelligence_maxxxing.governance import verify_manifest
from tests.conftest import REPO_ROOT


def test_constitution_manifest_matches() -> None:
    result = verify_manifest(REPO_ROOT / "docs" / "constitutional")
    assert result.ok, (
        "Constitutional manifest mismatch. "
        f"mismatched={result.mismatched} missing={result.missing_files} "
        f"unlisted={result.unlisted_files}. "
        "Constitutional documents must never change silently."
    )
    assert len(result.matched) >= 7, "expected at least the seven foundational documents"
