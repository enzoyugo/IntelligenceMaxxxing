"""Append-only M3B store (IM-owned; never TMX paths). Idempotent by output_hash."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def default_m3b_dir() -> Path:
    override = os.environ.get("IM_RESEARCH_M3B_STORE_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[4] / "data" / "research_factory_m3b"


class ResearchM3BStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or default_m3b_dir()
        self.evidence_bundles = self.root / "evidence_bundles.jsonl"
        self.safety_audits = self.root / "safety_audits.jsonl"
        self.structured_reports = self.root / "structured_reports.jsonl"
        self.audit_log = self.root / "audit_log.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)

    def _append(self, path: Path, row: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":"), ensure_ascii=True) + "\n")

    def _read(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows

    def _find_by_output_hash(self, path: Path, output_hash: str) -> dict[str, Any] | None:
        if not output_hash:
            return None
        for row in self._read(path):
            if row.get("output_hash") == output_hash:
                return row
        return None

    def append_idempotent(
        self,
        path: Path,
        row: dict[str, Any],
        *,
        id_key: str,
    ) -> tuple[dict[str, Any], bool]:
        """Append row unless identical output_hash already stored. Returns (row, created)."""
        existing = self._find_by_output_hash(path, str(row.get("output_hash") or ""))
        if existing is not None:
            return existing, False
        self._append(path, row)
        return row, True

    def append_evidence_bundle(self, row: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        return self.append_idempotent(self.evidence_bundles, row, id_key="bundle_id")

    def append_safety_audit(self, row: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        return self.append_idempotent(self.safety_audits, row, id_key="audit_id")

    def append_structured_report(self, row: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        return self.append_idempotent(self.structured_reports, row, id_key="report_id")

    def append_audit(self, row: dict[str, Any]) -> None:
        self._append(self.audit_log, row)

    def list_evidence_bundles(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self._read(self.evidence_bundles)[-limit:]

    def get_evidence_bundle(self, bundle_id: str) -> dict[str, Any] | None:
        for row in reversed(self._read(self.evidence_bundles)):
            if row.get("bundle_id") == bundle_id:
                return row
        return None

    def list_safety_audits(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self._read(self.safety_audits)[-limit:]

    def get_safety_audit(self, audit_id: str) -> dict[str, Any] | None:
        for row in reversed(self._read(self.safety_audits)):
            if row.get("audit_id") == audit_id:
                return row
        return None

    def list_structured_reports(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self._read(self.structured_reports)[-limit:]

    def get_structured_report(self, report_id: str) -> dict[str, Any] | None:
        for row in reversed(self._read(self.structured_reports)):
            if row.get("report_id") == report_id:
                return row
        return None

    def counts(self) -> dict[str, int]:
        return {
            "evidence_bundles": len(self._read(self.evidence_bundles)),
            "safety_audits": len(self._read(self.safety_audits)),
            "structured_reports": len(self._read(self.structured_reports)),
            "audit_log": len(self._read(self.audit_log)),
        }
