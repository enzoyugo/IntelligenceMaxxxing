"""Parallel research selective policy — TAKE/SKIP/ABSTAIN/DEFER (not Policy 1.0.0)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from intelligence_maxxxing.domain_packs.trading.meta_edge_v1 import (
    LIVE_POLICY_INFLUENCE,
    PROMOTION_ELIGIBLE,
    RESEARCH_BUNDLE_ID,
    RESEARCH_POLICY_ID,
)
from intelligence_maxxxing.domain_packs.trading.meta_edge_v1.base_rate_store import BaseRateStoreV1
from intelligence_maxxxing.domain_packs.trading.meta_edge_v1.contracts import (
    CONTRACT_VERSIONS,
    validate_observation,
)

TAKE_THRESHOLD_NET_R = 0.05
SKIP_THRESHOLD_NET_R = -0.05
MIN_EVIDENCE_N = 30


def policy_manifest() -> dict[str, Any]:
    return {
        "policy_id": RESEARCH_POLICY_ID,
        "bundle_id": RESEARCH_BUNDLE_ID,
        "promotion_eligible": PROMOTION_ELIGIBLE,
        "live_policy_influence": LIVE_POLICY_INFLUENCE,
        "take_threshold_net_R": TAKE_THRESHOLD_NET_R,
        "skip_threshold_net_R": SKIP_THRESHOLD_NET_R,
        "min_evidence_n": MIN_EVIDENCE_N,
        "research_only": True,
        "execution_enabled": False,
    }


def policy_hash() -> str:
    return hashlib.sha256(
        json.dumps(policy_manifest(), sort_keys=True).encode("utf-8")
    ).hexdigest()


def assess_observation(
    observation: dict[str, Any],
    store: BaseRateStoreV1,
    *,
    feature_registry_hash: str,
    split_hash: str,
) -> dict[str, Any]:
    errors = validate_observation(observation)
    reasons: list[str] = []
    if errors:
        return {
            "contract": CONTRACT_VERSIONS["assessment"],
            "policy_id": RESEARCH_POLICY_ID,
            "policy_hash": policy_hash(),
            "economic_setup_id": observation.get("economic_setup_id"),
            "decision": "DEFER_DATA_QUALITY",
            "rank_score": None,
            "expected_net_R": None,
            "uncertainty": 1.0,
            "eligible": False,
            "reasons": errors,
            "evidence_refs": [RESEARCH_POLICY_ID],
            "feature_registry_hash": feature_registry_hash,
            "split_hash": split_hash,
            "base_rate_level": None,
            "promotion_eligible": False,
            "live_policy_influence": False,
        }

    if observation.get("feature_registry_hash") and observation.get("feature_registry_hash") != feature_registry_hash:
        reasons.append("FEATURE_REGISTRY_MISMATCH")
        decision = "DEFER_DATA_QUALITY"
        br: dict[str, Any] = {"expected_net_R": None, "n": 0, "level": None, "sufficient": False}
    elif observation.get("split_hash") and observation.get("split_hash") != split_hash:
        reasons.append("SPLIT_HASH_MISMATCH")
        decision = "DEFER_DATA_QUALITY"
        br = {"expected_net_R": None, "n": 0, "level": None, "sufficient": False}
    else:
        br = store.lookup(observation)
        exp = br.get("expected_net_R")
        n = int(br.get("n") or 0)
        if not br.get("sufficient") or exp is None or n < MIN_EVIDENCE_N:
            decision = "ABSTAIN"
            reasons.append("SAMPLE_GATE_FAILED" if n < MIN_EVIDENCE_N else "BASE_RATE_INSUFFICIENT")
        elif float(exp) >= TAKE_THRESHOLD_NET_R:
            decision = "TAKE"
            reasons.append("EXPECTED_NET_R_ABOVE_TAKE")
        elif float(exp) <= SKIP_THRESHOLD_NET_R:
            decision = "SKIP"
            reasons.append("EXPECTED_NET_R_BELOW_SKIP")
        else:
            decision = "ABSTAIN"
            reasons.append("EXPECTED_NET_R_IN_ABSTENTION_BAND")

    exp = br.get("expected_net_R")
    n = int(br.get("n") or 0)
    uncertainty = 1.0 if n <= 0 else min(1.0, max(0.05, 1.0 / (n**0.5)))
    rank = None if exp is None else max(0.0, min(1.0, 0.5 + float(exp) / 2.0))

    return {
        "contract": CONTRACT_VERSIONS["assessment"],
        "policy_id": RESEARCH_POLICY_ID,
        "policy_hash": policy_hash(),
        "economic_setup_id": observation.get("economic_setup_id"),
        "decision": decision,
        "rank_score": None if rank is None else round(rank, 4),
        "expected_net_R": None if exp is None else round(float(exp), 6),
        "uncertainty": round(uncertainty, 4),
        "eligible": decision == "TAKE",
        "reasons": reasons,
        "evidence_refs": [RESEARCH_POLICY_ID, "base_rate_store_v1"],
        "feature_registry_hash": feature_registry_hash,
        "split_hash": split_hash,
        "base_rate_level": br.get("level"),
        "base_rate_n": n,
        "promotion_eligible": False,
        "live_policy_influence": False,
        "limitations": ["RESEARCH_ONLY", "NOT_LIVE_POLICY", "NOT_A_WIN_PROBABILITY"],
    }
