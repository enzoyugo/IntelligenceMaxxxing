"""Reproducible SHA-256 verification of the constitutional manifest.

The manifest file lists `<sha256>  <relative posix path>` per line, covering
every file under docs/constitutional except the manifest itself.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

MANIFEST_FILENAME = "CONSTITUTIONAL_MANIFEST.sha256"


@dataclass(frozen=True)
class ManifestEntry:
    relative_path: str
    sha256: str


@dataclass(frozen=True)
class ManifestVerification:
    ok: bool
    matched: tuple[str, ...]
    mismatched: tuple[str, ...]
    missing_files: tuple[str, ...]
    unlisted_files: tuple[str, ...]


def compute_manifest(constitutional_dir: Path) -> tuple[ManifestEntry, ...]:
    """Hash every constitutional file, sorted by path for reproducibility."""
    entries = []
    for path in sorted(constitutional_dir.rglob("*")):
        if path.is_file() and path.name != MANIFEST_FILENAME:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            entries.append(
                ManifestEntry(
                    relative_path=path.relative_to(constitutional_dir).as_posix(),
                    sha256=digest,
                )
            )
    return tuple(entries)


def _parse_manifest(manifest_path: Path) -> dict[str, str]:
    listed: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        digest, _, relative = line.partition("  ")
        if not digest or not relative:
            raise ValueError(f"malformed manifest line: {line!r}")
        listed[relative.strip()] = digest.strip()
    return listed


def verify_manifest(constitutional_dir: Path) -> ManifestVerification:
    """Compare the stored manifest against freshly computed hashes."""
    manifest_path = constitutional_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        return ManifestVerification(
            ok=False,
            matched=(),
            mismatched=(),
            missing_files=(MANIFEST_FILENAME,),
            unlisted_files=(),
        )

    listed = _parse_manifest(manifest_path)
    actual = {entry.relative_path: entry.sha256 for entry in compute_manifest(constitutional_dir)}

    matched = tuple(p for p, d in listed.items() if actual.get(p) == d)
    mismatched = tuple(p for p, d in listed.items() if p in actual and actual[p] != d)
    missing = tuple(p for p in listed if p not in actual)
    unlisted = tuple(p for p in actual if p not in listed)

    ok = not mismatched and not missing and not unlisted and bool(matched)
    return ManifestVerification(
        ok=ok,
        matched=matched,
        mismatched=mismatched,
        missing_files=missing,
        unlisted_files=unlisted,
    )


def find_constitutional_dir(start: Path) -> Path:
    """Locate docs/constitutional walking up from `start`."""
    for candidate in (start, *start.parents):
        target = candidate / "docs" / "constitutional"
        if target.is_dir():
            return target
    raise FileNotFoundError("docs/constitutional not found above " + str(start))
