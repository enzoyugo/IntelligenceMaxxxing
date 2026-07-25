"""Train / infer entrypoints over IM-local research storage only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from intelligence_maxxxing.domain_packs.trading.meta_edge_v1 import RESEARCH_POLICY_ID
from intelligence_maxxxing.domain_packs.trading.meta_edge_v1.base_rate_store import BaseRateStoreV1
from intelligence_maxxxing.domain_packs.trading.meta_edge_v1.contracts import (
    CONTRACT_VERSIONS,
    validate_training_row,
)
from intelligence_maxxxing.domain_packs.trading.meta_edge_v1.model_suite import RidgeExpectancyModelV1
from intelligence_maxxxing.domain_packs.trading.meta_edge_v1.selective_policy import (
    assess_observation,
    policy_hash,
    policy_manifest,
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def train_from_inbox(
    *,
    inbox_training_jsonl: Path,
    artifact_dir: Path,
    split_hash: str,
    feature_registry_hash: str,
) -> dict[str, Any]:
    rows = _read_jsonl(inbox_training_jsonl)
    clean: list[dict[str, Any]] = []
    rejected = 0
    for row in rows:
        errs = validate_training_row(row)
        if errs:
            rejected += 1
            continue
        clean.append(row)

    store = BaseRateStoreV1()
    store.fit(clean, split_hash=split_hash)
    model = RidgeExpectancyModelV1(lam=1.0)
    model.fit(clean)

    artifact_dir.mkdir(parents=True, exist_ok=True)
    store_path = artifact_dir / "base_rate_store.json"
    model_path = artifact_dir / "ridge_model.json"
    policy_path = artifact_dir / "policy_artifact.json"
    store_hash = store.save(store_path)
    model_path.write_text(json.dumps(model.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    policy_art = {
        "contract": CONTRACT_VERSIONS["policy_artifact"],
        "policy": policy_manifest(),
        "policy_hash": policy_hash(),
        "base_rate_hash": store_hash,
        "model_hash": model.artifact_hash(),
        "split_hash": split_hash,
        "feature_registry_hash": feature_registry_hash,
        "n_train_rows": len(clean),
        "n_rejected": rejected,
        "policy_id": RESEARCH_POLICY_ID,
    }
    policy_path.write_text(json.dumps(policy_art, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt = {
        "status": "TRAINED",
        "n_train_rows": len(clean),
        "n_rejected": rejected,
        "store_path": str(store_path),
        "model_path": str(model_path),
        "policy_path": str(policy_path),
        "base_rate_hash": store_hash,
        "model_hash": model.artifact_hash(),
        "policy_hash": policy_hash(),
    }
    (artifact_dir / "train_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def infer_from_observations(
    *,
    observations_jsonl: Path,
    artifact_dir: Path,
    out_assessments_jsonl: Path,
) -> dict[str, Any]:
    policy_art = json.loads((artifact_dir / "policy_artifact.json").read_text(encoding="utf-8"))
    store = BaseRateStoreV1.load(artifact_dir / "base_rate_store.json")
    feature_registry_hash = str(policy_art["feature_registry_hash"])
    split_hash = str(policy_art["split_hash"])
    rows = _read_jsonl(observations_jsonl)
    assessments = [
        assess_observation(
            row,
            store,
            feature_registry_hash=feature_registry_hash,
            split_hash=split_hash,
        )
        for row in rows
    ]
    _write_jsonl(out_assessments_jsonl, assessments)
    summary = {
        "n_observations": len(rows),
        "n_assessments": len(assessments),
        "decisions": _count(assessments, "decision"),
        "out_path": str(out_assessments_jsonl),
        "policy_hash": policy_art.get("policy_hash"),
    }
    (artifact_dir / "infer_receipt.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def _count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        k = str(row.get(key) or "NONE")
        out[k] = out.get(k, 0) + 1
    return out
