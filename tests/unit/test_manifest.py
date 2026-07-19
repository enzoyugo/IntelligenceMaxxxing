"""Unit tests for constitutional manifest verification."""

from pathlib import Path

from intelligence_maxxxing.governance import compute_manifest, verify_manifest
from intelligence_maxxxing.governance.manifest import MANIFEST_FILENAME


def _write_manifest(directory: Path) -> None:
    entries = compute_manifest(directory)
    content = "\n".join(f"{e.sha256}  {e.relative_path}" for e in entries) + "\n"
    (directory / MANIFEST_FILENAME).write_text(content, encoding="utf-8")


def test_verify_matches(tmp_path: Path) -> None:
    (tmp_path / "CONSTITUTION.md").write_text("hello", encoding="utf-8")
    _write_manifest(tmp_path)
    result = verify_manifest(tmp_path)
    assert result.ok
    assert result.matched == ("CONSTITUTION.md",)


def test_verify_detects_modification(tmp_path: Path) -> None:
    doc = tmp_path / "CONSTITUTION.md"
    doc.write_text("hello", encoding="utf-8")
    _write_manifest(tmp_path)
    doc.write_text("tampered", encoding="utf-8")
    result = verify_manifest(tmp_path)
    assert not result.ok
    assert result.mismatched == ("CONSTITUTION.md",)


def test_verify_detects_unlisted_file(tmp_path: Path) -> None:
    (tmp_path / "CONSTITUTION.md").write_text("hello", encoding="utf-8")
    _write_manifest(tmp_path)
    (tmp_path / "SNEAKY_NEW_DOC.md").write_text("new", encoding="utf-8")
    result = verify_manifest(tmp_path)
    assert not result.ok
    assert result.unlisted_files == ("SNEAKY_NEW_DOC.md",)


def test_verify_detects_missing_manifest(tmp_path: Path) -> None:
    result = verify_manifest(tmp_path)
    assert not result.ok
    assert MANIFEST_FILENAME in result.missing_files
