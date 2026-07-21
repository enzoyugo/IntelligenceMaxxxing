"""IM_TRADING_DECISION_POLICY 1.0.0 â€” deterministic, frozen, auditable."""

from __future__ import annotations

import hashlib
import json
from typing import Any

POLICY_ID = "IM_TRADING_DECISION_POLICY"
POLICY_VERSION = "1.0.0"
POLICY_FROZEN_AT = "2026-07-20T22:00:00Z"
MODEL_VERSION = None

# Frozen ruleset identity (hash of gate order + thresholds).
_RULESET_CANONICAL = {
    "policy_id": POLICY_ID,
    "policy_version": POLICY_VERSION,
    "gates": [
        "schema_provenance",
        "temporal_validity",
        "economic_identity",
        "quote_quality",
        "cost_quality",
        "fidelity",
        "evidence_sufficiency",
        "context_support",
        "portfolio_concentration",
        "known_anomalies",
        "rank",
        "decision",
    ],
    "take_threshold": 0.55,
    "skip_threshold": 0.45,
}
RULESET_HASH = hashlib.sha256(
    json.dumps(_RULESET_CANONICAL, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()

TAKE_THRESHOLD = 0.55
SKIP_THRESHOLD = 0.45

FORBIDDEN_OUTCOME_KEYS = frozenset(
    {
        "outcome",
        "exit_reason",
        "exit_time",
        "realized_R",
        "gross_R",
        "trusted_net_R",
        "net_R",
        "mfe",
        "mae",
        "resolved_at",
        "pnl",
    }
)


def _has_forbidden(obj: Any, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            here = f"{path}.{k}" if path else str(k)
            if k in FORBIDDEN_OUTCOME_KEYS:
                hits.append(here)
            hits.extend(_has_forbidden(v, here))
    return hits


def assess_observation(observation: dict[str, Any]) -> dict[str, Any]:
    """Run ordered gates. Does not tune for decision distribution."""
    reasons: list[str] = []
    evidence_refs: list[str] = []
    decision = "UNKNOWN"
    rank_score: float | None = None
    eligible = False

    # 1 schema/provenance
    if observation.get("schema_version") != "tmx.im.observation.v1":
        return _defer(
            "SCHEMA_INVALID",
            reasons=["SCHEMA_PROVENANCE_FAILED"],
            data_trust=0.0,
            evidence=0.0,
        )
    if observation.get("source_system") != "TradingMaxxxing":
        return _defer(
            "SCHEMA_INVALID",
            reasons=["SOURCE_SYSTEM_INVALID"],
            data_trust=0.0,
            evidence=0.0,
        )
    leaks = _has_forbidden(observation)
    if leaks:
        return _defer(
            "OUTCOME_LEAKAGE",
            reasons=["OUTCOME_OR_FUTURE_FIELD_PRESENT", *leaks[:4]],
            data_trust=0.0,
            evidence=0.0,
        )

    # 2 temporal validity
    cutoff = str(observation.get("decision_cutoff_utc") or "")
    features = observation.get("features") or {}
    future_feats = []
    if isinstance(features, dict):
        for name, feat in features.items():
            if not isinstance(feat, dict):
                continue
            avail = str(feat.get("available_at_utc") or "")
            if cutoff and avail and avail > cutoff:
                future_feats.append(name)
    if future_feats:
        return _defer(
            "FUTURE_FEATURE",
            reasons=["TEMPORAL_INVALID", *[f"FUTURE_FEATURE:{n}" for n in future_feats[:4]]],
            data_trust=0.1,
            evidence=0.0,
        )

    setup = observation.get("economic_setup") or {}
    dq = observation.get("data_quality") or {}

    # 3 economic identity
    if not setup.get("economic_setup_id"):
        return _defer("MISSING_ECONOMIC_SETUP_ID", reasons=["ECONOMIC_IDENTITY_FAILED"], data_trust=0.2, evidence=0.0)
    if setup.get("nominal_risk_R") != 1.0:
        return _defer("NOMINAL_RISK_NOT_1R", reasons=["ECONOMIC_IDENTITY_FAILED"], data_trust=0.2, evidence=0.0)
    evidence_refs.append(f"setup:{setup.get('economic_setup_id')}")

    # 4 quote quality
    quote_q = str(dq.get("quote_quality") or "").upper()
    if quote_q in {"", "QUOTE_UNAVAILABLE", "QUOTE_MISSING", "NONE"}:
        return _defer(
            "QUOTE_QUALITY_INCOMPLETE",
            reasons=["DEFER_DATA_QUALITY", "QUOTE_QUALITY_GATE"],
            data_trust=0.3,
            evidence=0.2,
        )
    if quote_q in {"QUOTE_FUTURE_REJECTED"}:
        return _defer(
            "QUOTE_FUTURE_REJECTED",
            reasons=["DEFER_DATA_QUALITY", "QUOTE_FUTURE_REJECTED"],
            data_trust=0.2,
            evidence=0.1,
        )

    # 5 cost quality â€” incomplete does not invent 0; may still assess with defer-for-economics
    cost_q = str(dq.get("cost_quality") or "").upper()
    cost_incomplete = cost_q in {"", "COST_UNAVAILABLE", "NONE", "COST_INCOMPLETE"}

    # 6 fidelity
    fidelity = str(setup.get("strategy_fidelity_class") or "PARTIAL").upper()
    if fidelity == "DEPRECATED":
        reasons.append("FIDELITY_DEPRECATED_EXCLUDED")
        return _result(
            decision="SKIP",
            rank_score=0.0,
            reasons=reasons + ["FIDELITY_GATE"],
            evidence_refs=evidence_refs,
            data_trust=0.7,
            evidence=0.3,
            eligible=False,
            limitations=["DEPRECATED_FIDELITY"],
        )
    if fidelity == "PROXY":
        reasons.append("FIDELITY_PROXY_OBSERVATIONAL")
    if fidelity == "PARTIAL":
        reasons.append("FIDELITY_PARTIAL_SHADOW")

    # 7 evidence sufficiency â€” V1 has no trusted base-rate store yet
    evidence_strength = 0.25
    reasons.append("NO_TRUSTED_BASE_RATE")
    reasons.append("SAMPLE_TOO_SMALL")
    evidence_refs.append("policy:IM_TRADING_DECISION_POLICY@1.0.0")

    # 8 context support
    context = observation.get("market_context") or {}
    context_score = 0.5 if context.get("symbol") else 0.2

    # 9 portfolio concentration â€” research stub
    portfolio_ok = True

    # 10 known anomalies
    anomaly = False
    if quote_q == "QUOTE_STALE":
        reasons.append("QUOTE_STALE_ANOMALY")
        anomaly = True

    # 11 rank â€” simple deterministic score from available gates (not win probability)
    raw = observation.get("raw_strategy") or {}
    native = observation.get("tmx_native") or {}
    score = 0.35
    if raw.get("decision") == "TAKE":
        score += 0.15
    if native.get("decision") == "TAKE":
        score += 0.10
    if native.get("decision") == "SKIP":
        score -= 0.10
    if quote_q in {"QUOTE_VALID", "QUOTE_EXACT", "QUOTE_FRESH", "QUOTE_ACCEPTABLE"}:
        score += 0.10
    if anomaly:
        score -= 0.08
    if cost_incomplete:
        score -= 0.05
        reasons.append("COST_COVERAGE_INCOMPLETE")
    score = max(0.0, min(1.0, score))
    rank_score = round(score, 4)

    # 12 decision
    data_trust = 0.55 if not cost_incomplete else 0.45
    if quote_q in {"QUOTE_VALID", "QUOTE_EXACT", "QUOTE_FRESH"}:
        data_trust += 0.15
    data_trust = min(1.0, data_trust)

    if evidence_strength < 0.4:
        decision = "UNKNOWN"
        reasons.append("EVIDENCE_INSUFFICIENT")
        eligible = False
    elif rank_score >= TAKE_THRESHOLD and fidelity in {"CERTIFIED", "PARTIAL"}:
        decision = "TAKE"
        eligible = fidelity == "CERTIFIED" and not cost_incomplete
        reasons.append("SCORE_ABOVE_TAKE_THRESHOLD")
    elif rank_score <= SKIP_THRESHOLD:
        decision = "SKIP"
        eligible = False
        reasons.append("SCORE_BELOW_SKIP_THRESHOLD")
    else:
        decision = "UNKNOWN"
        reasons.append("SCORE_IN_ABSTENTION_BAND")
        eligible = False

    return _result(
        decision=decision,
        rank_score=rank_score,
        reasons=reasons,
        evidence_refs=evidence_refs,
        data_trust=data_trust,
        evidence=evidence_strength,
        eligible=eligible,
        context_confidence=context_score,
        limitations=[
            "NOT_A_WIN_PROBABILITY",
            "NO_TRUSTED_BASE_RATE",
            "POLICY_1_0_0_FROZEN",
        ],
    )


def _defer(code: str, *, reasons: list[str], data_trust: float, evidence: float) -> dict[str, Any]:
    return _result(
        decision="DEFER_DATA_QUALITY",
        rank_score=None,
        reasons=[code, *reasons],
        evidence_refs=[],
        data_trust=data_trust,
        evidence=evidence,
        eligible=False,
        limitations=["DEFER_DATA_QUALITY", "NOT_A_WIN_PROBABILITY"],
    )


def _result(
    *,
    decision: str,
    rank_score: float | None,
    reasons: list[str],
    evidence_refs: list[str],
    data_trust: float,
    evidence: float,
    eligible: bool,
    context_confidence: float = 0.5,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    # UNKNOWN must not collapse to confidence 0.
    overall: float | None
    if decision == "UNKNOWN":
        overall = None
    elif decision == "DEFER_DATA_QUALITY":
        overall = None
    else:
        overall = round((data_trust + evidence + context_confidence) / 3.0, 4)
    return {
        "decision": decision,
        "rank_score": rank_score,
        "data_trust": round(data_trust, 4),
        "evidence_strength": round(evidence, 4),
        "confidence_components": {
            "data_trust_confidence": round(data_trust, 4),
            "evidence_confidence": round(evidence, 4),
            "context_confidence": round(context_confidence, 4),
            "statistical_confidence": None,
            "calibration_confidence": None,
            "model_confidence": None,
            "method": "deterministic_gate_v1",
            "limitations": limitations or ["NOT_A_WIN_PROBABILITY"],
        },
        "overall_confidence": overall,
        "eligible_for_economic_evaluation": eligible,
        "reason_codes": reasons,
        "evidence_refs": evidence_refs,
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "policy_frozen_at_utc": POLICY_FROZEN_AT,
        "ruleset_hash": RULESET_HASH,
        "model_version": MODEL_VERSION,
        "prompt_hash": None,
    }
