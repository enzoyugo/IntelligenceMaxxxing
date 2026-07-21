"""Append-only trading observation/assessment store (IM-owned; no TMX paths)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def default_trading_dir() -> Path:
    override = os.environ.get("IM_TRADING_STORE_DIR")
    if override:
        return Path(override)
    # Local engine data under repo (not TMX).
    return Path(__file__).resolve().parents[4] / "data" / "trading_bridge_v1"


class TradingJsonlStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or default_trading_dir()
        self.observations = self.root / "trading_observations.jsonl"
        self.assessments = self.root / "trading_assessments.jsonl"
        self.idempotency = self.root / "trading_idempotency.jsonl"
        self.evidence = self.root / "trading_evidence_bundles.jsonl"
        self.policy_registry = self.root / "policy_registry.json"
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

    def find_idempotency(self, key: str) -> dict[str, Any] | None:
        for row in self._read(self.idempotency):
            if row.get("idempotency_key") == key:
                return row
        return None

    def save_idempotency(self, row: dict[str, Any]) -> None:
        self._append(self.idempotency, row)

    def save_observation(self, row: dict[str, Any]) -> None:
        self._append(self.observations, row)

    def save_assessment(self, row: dict[str, Any]) -> None:
        self._append(self.assessments, row)

    def get_assessment(self, assessment_id: str) -> dict[str, Any] | None:
        for row in self._read(self.assessments):
            if row.get("assessment_id") == assessment_id:
                return row
        return None

    def counts(self) -> dict[str, int]:
        return {
            "observations": len(self._read(self.observations)),
            "assessments": len(self._read(self.assessments)),
            "idempotency_keys": len(self._read(self.idempotency)),
        }
