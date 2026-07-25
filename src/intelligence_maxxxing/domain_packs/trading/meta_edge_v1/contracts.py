"""Versioned research contracts for meta-edge discovery (IM side)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

CONTRACT_VERSIONS = {
    "dataset_manifest": "tmx.im.meta_edge_dataset_manifest.v1",
    "training_row": "tmx.im.meta_edge_training_row.v1",
    "observation": "tmx.im.meta_edge_observation.v1",
    "assessment": "im.tmx.meta_edge_assessment.v1",
    "policy_artifact": "im.tmx.meta_edge_policy_artifact.v1",
}

ALLOWED_TRAINING_ORIGINS = frozenset({"TRAIN", "CALIBRATION", "VALIDATION_EVAL"})
FORBIDDEN_ORIGINS = frozenset({"TEST_OOS", "OOS", "OOS_TEST_FROZEN", "FORWARD", "FORWARD_PAPER"})

OUTCOME_FIELDS = frozenset(
    {
        "gross_R",
        "trusted_R",
        "trusted_net_R",
        "cost_R",
        "MFE_R",
        "MAE_R",
        "resolved_R",
        "outcome_status",
        "final_cost_R",
        "label_trusted_net_R",
    }
)


def schema_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def assert_origin_allowed(origin: str, *, for_training: bool) -> None:
    o = str(origin or "").upper()
    if o in FORBIDDEN_ORIGINS:
        raise ValueError(f"FORBIDDEN_ORIGIN:{o}")
    if for_training and o not in ALLOWED_TRAINING_ORIGINS:
        raise ValueError(f"TRAINING_ORIGIN_REJECTED:{o}")


def strip_outcomes(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k not in OUTCOME_FIELDS}


def validate_observation(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if row.get("contract") != CONTRACT_VERSIONS["observation"]:
        errors.append("CONTRACT_MISMATCH")
    for field in OUTCOME_FIELDS:
        if field in row and row[field] is not None:
            errors.append(f"OUTCOME_LEAK:{field}")
    origin = str(row.get("origin") or "").upper()
    if origin in FORBIDDEN_ORIGINS:
        errors.append(f"FORBIDDEN_ORIGIN:{origin}")
    return errors


def validate_training_row(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if row.get("contract") != CONTRACT_VERSIONS["training_row"]:
        errors.append("CONTRACT_MISMATCH")
    try:
        assert_origin_allowed(str(row.get("origin") or ""), for_training=True)
    except ValueError as exc:
        errors.append(str(exc))
    if "label_trusted_net_R" not in row:
        errors.append("MISSING_LABEL")
    return errors
