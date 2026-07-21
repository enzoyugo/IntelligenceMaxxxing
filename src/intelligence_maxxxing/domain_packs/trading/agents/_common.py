"""Shared helpers for M2 agents (deterministic hashing, PIT gates)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from intelligence_maxxxing.domain_packs.trading.policy_v1 import FORBIDDEN_OUTCOME_KEYS

FORBIDDEN_OUTCOME_KEYS_LOCAL = FORBIDDEN_OUTCOME_KEYS


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def content_hash(obj: Any) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def has_forbidden_outcome_fields(obj: Any, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            here = f"{path}.{k}" if path else str(k)
            if k in FORBIDDEN_OUTCOME_KEYS_LOCAL:
                hits.append(here)
            hits.extend(has_forbidden_outcome_fields(v, here))
    return hits


def pit_feature_violations(observation: dict[str, Any]) -> list[str]:
    cutoff = str(observation.get("decision_cutoff_utc") or "")
    violations: list[str] = []
    features = observation.get("features") or {}
    if not isinstance(features, dict):
        return ["FEATURES_NOT_OBJECT"]
    for name, feat in features.items():
        if not isinstance(feat, dict):
            continue
        observed = str(feat.get("observed_at_utc") or "")
        available = str(feat.get("available_at_utc") or "")
        if cutoff and observed and observed > cutoff:
            violations.append(f"OBSERVED_AFTER_CUTOFF:{name}")
        if cutoff and available and available > cutoff:
            violations.append(f"AVAILABLE_AFTER_CUTOFF:{name}")
    return violations


def feature_value(observation: dict[str, Any], name: str) -> Any:
    features = observation.get("features") or {}
    if not isinstance(features, dict):
        return None
    feat = features.get(name)
    if isinstance(feat, dict):
        return feat.get("value")
    return None


def session_from_context(observation: dict[str, Any]) -> str:
    ctx = observation.get("market_context") or {}
    label = str(ctx.get("session") or feature_value(observation, "session_label") or "").upper()
    allowed = {"ASIA", "LONDON", "NEW_YORK", "OVERLAP", "TRANSITION", "UNKNOWN"}
    if label in allowed:
        return label
    # Deterministic hour bucket from cutoff if present (UTC).
    cutoff = str(observation.get("decision_cutoff_utc") or "")
    try:
        hour = int(cutoff[11:13])
    except (ValueError, IndexError):
        return "UNKNOWN"
    if 0 <= hour < 7:
        return "ASIA"
    if 7 <= hour < 12:
        return "LONDON"
    if 12 <= hour < 16:
        return "OVERLAP"
    if 16 <= hour < 21:
        return "NEW_YORK"
    return "TRANSITION"
