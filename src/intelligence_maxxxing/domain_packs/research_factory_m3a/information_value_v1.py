"""Deterministic Information Value score — prioritizes research, never executes."""

from __future__ import annotations

from typing import Any

from intelligence_maxxxing.domain_packs.research_factory_m3a.hashes import content_hash


def score_information_value(payload: dict[str, Any]) -> dict[str, Any]:
    """Explainable IV. Does not use expected profit as sole criterion."""
    components = {
        "uncertainty_reduction": _clip(float(payload.get("uncertainty_reduction", 0.4))),
        "decision_relevance": _clip(float(payload.get("decision_relevance", 0.4))),
        "data_quality_readiness": _clip(float(payload.get("data_quality_readiness", 0.3))),
        "feasibility": _clip(float(payload.get("feasibility", 0.5))),
        "sample_gap": _clip(float(payload.get("sample_gap", 0.5))),
        "novelty": _clip(float(payload.get("novelty", 0.4))),
        "contradiction_value": _clip(float(payload.get("contradiction_value", 0.3))),
        "cross_strategy_value": _clip(float(payload.get("cross_strategy_value", 0.3))),
        "resource_cost": _clip(float(payload.get("resource_cost", 0.4))),
        "time_cost": _clip(float(payload.get("time_cost", 0.4))),
        "leakage_risk": _clip(float(payload.get("leakage_risk", 0.2))),
        "fidelity_readiness": _clip(float(payload.get("fidelity_readiness", 0.4))),
    }
    reasons: list[str] = []
    # Positive drivers
    raw = (
        0.14 * components["uncertainty_reduction"]
        + 0.14 * components["decision_relevance"]
        + 0.12 * components["data_quality_readiness"]
        + 0.10 * components["feasibility"]
        + 0.08 * components["sample_gap"]
        + 0.08 * components["novelty"]
        + 0.08 * components["contradiction_value"]
        + 0.06 * components["cross_strategy_value"]
        + 0.08 * components["fidelity_readiness"]
        - 0.10 * components["resource_cost"]
        - 0.08 * components["time_cost"]
        - 0.16 * components["leakage_risk"]
    )
    if components["leakage_risk"] >= 0.6:
        raw -= 0.15
        reasons.append("LEAKAGE_RISK_PENALTY")
    if components["data_quality_readiness"] < 0.35:
        raw -= 0.10
        reasons.append("LOW_DQ_PENALTY")
    if payload.get("expected_profit_only"):
        raw -= 0.20
        reasons.append("EXPECTED_PROFIT_ONLY_PENALTY")
    score = round(max(0.0, min(1.0, raw)), 4)
    if score >= 0.75:
        priority = "CRITICAL"
    elif score >= 0.55:
        priority = "HIGH"
    elif score >= 0.35:
        priority = "MEDIUM"
    else:
        priority = "LOW"
    if not reasons:
        reasons.append("DETERMINISTIC_IV_V1")
    body = {
        "information_value_score": score,
        "priority": priority,
        "reason_codes": reasons,
        "component_scores": components,
        "limitations": [
            "NOT_AN_EDGE_CLAIM",
            "DOES_NOT_EXECUTE_EXPERIMENTS",
            "DOES_NOT_CHANGE_TRADING_DECISIONS",
            "NOT_EXPECTED_PROFIT_RANKING",
        ],
        "live_control": False,
        "auto_run": False,
    }
    body["content_hash"] = content_hash(body)
    return body


def _clip(x: float) -> float:
    return max(0.0, min(1.0, float(x)))
