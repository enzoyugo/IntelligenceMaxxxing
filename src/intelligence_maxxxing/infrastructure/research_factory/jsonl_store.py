"""Append-only M3A research factory store (IM-owned; never TMX paths)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def default_research_dir() -> Path:
    override = os.environ.get("IM_RESEARCH_FACTORY_STORE_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[4] / "data" / "research_factory_m3a"


class ResearchFactoryStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or default_research_dir()
        self.hypotheses = self.root / "hypotheses.jsonl"
        self.evidence = self.root / "evidence.jsonl"
        self.experiments = self.root / "experiments.jsonl"
        self.learning = self.root / "learning_memory.jsonl"
        self.audit = self.root / "audit_log.jsonl"
        self.approvals = self.root / "manual_approvals.jsonl"
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

    def append_hypothesis(self, row: dict[str, Any]) -> None:
        self._append(self.hypotheses, row)

    def append_evidence(self, row: dict[str, Any]) -> None:
        self._append(self.evidence, row)

    def append_experiment(self, row: dict[str, Any]) -> None:
        self._append(self.experiments, row)

    def append_learning(self, row: dict[str, Any]) -> None:
        self._append(self.learning, row)

    def append_audit(self, row: dict[str, Any]) -> None:
        self._append(self.audit, row)

    def append_approval(self, row: dict[str, Any]) -> None:
        self._append(self.approvals, row)

    def list_hypotheses(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self._latest_by_id(self._read(self.hypotheses), "hypothesis_id", limit)

    def get_hypothesis(self, hypothesis_id: str) -> dict[str, Any] | None:
        latest = None
        for row in self._read(self.hypotheses):
            if row.get("hypothesis_id") == hypothesis_id:
                latest = row
        return latest

    def list_evidence(self, *, limit: int = 200, hypothesis_id: str | None = None) -> list[dict[str, Any]]:
        rows = self._read(self.evidence)
        if hypothesis_id:
            rows = [r for r in rows if r.get("hypothesis_id") == hypothesis_id]
        return rows[-limit:]

    def get_evidence(self, evidence_id: str) -> dict[str, Any] | None:
        for row in reversed(self._read(self.evidence)):
            if row.get("evidence_id") == evidence_id:
                return row
        return None

    def list_experiments(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self._latest_by_id(self._read(self.experiments), "experiment_id", limit)

    def get_experiment(self, experiment_id: str) -> dict[str, Any] | None:
        latest = None
        for row in self._read(self.experiments):
            if row.get("experiment_id") == experiment_id:
                latest = row
        return latest

    def list_learning(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self._read(self.learning)[-limit:]

    def counts(self) -> dict[str, int]:
        return {
            "hypotheses_versions": len(self._read(self.hypotheses)),
            "hypotheses_unique": len({r.get("hypothesis_id") for r in self._read(self.hypotheses)}),
            "evidence": len(self._read(self.evidence)),
            "experiments_versions": len(self._read(self.experiments)),
            "learning": len(self._read(self.learning)),
            "approvals": len(self._read(self.approvals)),
        }

    @staticmethod
    def _latest_by_id(rows: list[dict[str, Any]], key: str, limit: int) -> list[dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            kid = str(row.get(key) or "")
            if kid:
                latest[kid] = row
        out = list(latest.values())
        return out[-limit:]
