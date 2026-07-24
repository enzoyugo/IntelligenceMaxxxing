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
        # M2 append-only agent artifacts (never write TMX storage).
        self.context_assessments = self.root / "trading_context_assessments.jsonl"
        self.anomaly_findings = self.root / "trading_anomaly_findings.jsonl"
        self.critic_reviews = self.root / "trading_critic_reviews.jsonl"
        self.shadow_adjudications = self.root / "trading_shadow_adjudications.jsonl"
        self.agent_bundle_registry = self.root / "agent_bundle_registry.jsonl"
        self.agent_runs = self.root / "agent_runs.jsonl"
        self.agent_health_snapshots = self.root / "agent_health_snapshots.jsonl"
        self.retrospective_replay_manifests = self.root / "retrospective_replay_manifests.jsonl"
        # Observational HorizonNoise sidecar (outside frozen M2 decision bundle).
        self.horizon_noise_assessments = self.root / "trading_horizon_noise_assessments.jsonl"
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

    def agent_counts(self) -> dict[str, int]:
        return {
            "context_assessments": len(self._read(self.context_assessments)),
            "anomaly_findings": len(self._read(self.anomaly_findings)),
            "critic_reviews": len(self._read(self.critic_reviews)),
            "shadow_adjudications": len(self._read(self.shadow_adjudications)),
            "horizon_noise_assessments": len(self._read(self.horizon_noise_assessments)),
            "agent_runs": len(self._read(self.agent_runs)),
        }

    def save_context_assessment(self, row: dict[str, Any]) -> None:
        self._append(self.context_assessments, row)

    def get_context_assessment(self, context_assessment_id: str) -> dict[str, Any] | None:
        for row in self._read(self.context_assessments):
            if row.get("context_assessment_id") == context_assessment_id:
                return row
        return None

    def save_anomaly_finding(self, row: dict[str, Any]) -> None:
        self._append(self.anomaly_findings, row)

    def get_anomaly_finding(self, finding_id: str) -> dict[str, Any] | None:
        for row in self._read(self.anomaly_findings):
            if row.get("finding_id") == finding_id:
                return row
        return None

    def save_critic_review(self, row: dict[str, Any]) -> None:
        self._append(self.critic_reviews, row)

    def get_critic_review(self, critic_review_id: str) -> dict[str, Any] | None:
        for row in self._read(self.critic_reviews):
            if row.get("critic_review_id") == critic_review_id:
                return row
        return None

    def save_shadow_adjudication(self, row: dict[str, Any]) -> None:
        self._append(self.shadow_adjudications, row)

    def get_shadow_adjudication(self, shadow_adjudication_id: str) -> dict[str, Any] | None:
        for row in self._read(self.shadow_adjudications):
            if row.get("shadow_adjudication_id") == shadow_adjudication_id:
                return row
        return None

    def save_agent_run(self, row: dict[str, Any]) -> None:
        self._append(self.agent_runs, row)

    def save_horizon_noise_assessment(self, row: dict[str, Any]) -> None:
        self._append(self.horizon_noise_assessments, row)

    def get_horizon_noise_assessment(self, horizon_assessment_id: str) -> dict[str, Any] | None:
        for row in self._read(self.horizon_noise_assessments):
            if row.get("horizon_assessment_id") == horizon_assessment_id:
                return row
        return None

    def save_agent_bundle_registry(self, row: dict[str, Any]) -> None:
        self._append(self.agent_bundle_registry, row)

    def save_retrospective_replay_manifest(self, row: dict[str, Any]) -> None:
        self._append(self.retrospective_replay_manifests, row)
