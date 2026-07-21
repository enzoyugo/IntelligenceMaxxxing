"""ContextAgentV1 — structured market context; no outcome prediction."""

from __future__ import annotations

from typing import Any

from intelligence_maxxxing.domain_packs.trading.agent_bundle_v1 import (
    AGENT_BUNDLE_VERSION,
    CONTEXT_SCHEMA_VERSION,
    THRESHOLDS,
)
from intelligence_maxxxing.domain_packs.trading.agents._common import (
    content_hash,
    feature_value,
    has_forbidden_outcome_fields,
    new_id,
    pit_feature_violations,
    session_from_context,
    utc_now,
)

AGENT_ID = "ContextAgentV1"
AGENT_VERSION = "1.0.0"


def _vol_bucket(observation: dict[str, Any]) -> str:
    raw = feature_value(observation, "volatility_bucket")
    if raw is not None:
        token = str(raw).upper()
        if token in {"VERY_LOW", "LOW", "NORMAL", "HIGH", "EXTREME", "UNKNOWN"}:
            return token
    spread = feature_value(observation, "spread_price")
    try:
        s = float(spread) if spread is not None else None
    except (TypeError, ValueError):
        s = None
    if s is None:
        return "UNKNOWN"
    if s >= THRESHOLDS["spread_extreme"]:
        return "EXTREME"
    if s >= THRESHOLDS["spread_high"]:
        return "HIGH"
    if s <= THRESHOLDS["spread_high"] * 0.3:
        return "LOW"
    return "NORMAL"


def _spread_state(observation: dict[str, Any]) -> str:
    bucket = feature_value(observation, "spread_bucket")
    if bucket is not None:
        token = str(bucket).upper()
        if token in {"LOW", "NORMAL", "HIGH", "EXTREME", "UNKNOWN"}:
            return token
    spread = feature_value(observation, "spread_price")
    try:
        s = float(spread) if spread is not None else None
    except (TypeError, ValueError):
        s = None
    if s is None:
        return "UNKNOWN"
    if s >= THRESHOLDS["spread_extreme"]:
        return "EXTREME"
    if s >= THRESHOLDS["spread_high"]:
        return "HIGH"
    if s <= THRESHOLDS["spread_high"] * 0.4:
        return "LOW"
    return "NORMAL"


def _trend(observation: dict[str, Any]) -> str:
    raw = feature_value(observation, "trend_label")
    if raw is not None:
        token = str(raw).upper()
        if token in {"UP", "DOWN", "RANGE", "TRANSITION", "UNKNOWN"}:
            return token
    direction = str((observation.get("economic_setup") or {}).get("direction") or "").upper()
    if direction in {"LONG", "BUY"}:
        return "UP"
    if direction in {"SHORT", "SELL"}:
        return "DOWN"
    return "UNKNOWN"


def _liquidity(observation: dict[str, Any]) -> str:
    raw = feature_value(observation, "liquidity_label")
    if raw is not None:
        token = str(raw).upper()
        if token in {"THIN", "NORMAL", "DEEP", "UNKNOWN"}:
            return token
    spread = _spread_state(observation)
    if spread in {"HIGH", "EXTREME"}:
        return "THIN"
    if spread == "LOW":
        return "DEEP"
    if spread == "NORMAL":
        return "NORMAL"
    return "UNKNOWN"


def _regime(session: str, vol: str, trend: str, spread: str) -> str:
    if vol == "EXTREME" or spread == "EXTREME":
        return "EVENT_RISK"
    if trend in {"UP", "DOWN"} and vol in {"HIGH", "NORMAL"}:
        return "TREND_EXPANSION"
    if trend in {"UP", "DOWN"} and vol in {"LOW", "VERY_LOW"}:
        return "TREND_PULLBACK"
    if trend == "RANGE" and vol in {"LOW", "VERY_LOW"}:
        return "RANGE_COMPRESSION"
    if trend == "RANGE" and vol in {"HIGH", "EXTREME"}:
        return "RANGE_EXPANSION"
    if trend == "TRANSITION":
        return "REVERSAL_RISK"
    if session == "UNKNOWN" and vol == "UNKNOWN":
        return "UNCLASSIFIED"
    return "UNCLASSIFIED"


class ContextAgentV1:
    agent_id = AGENT_ID
    agent_version = AGENT_VERSION

    def assess(self, observation: dict[str, Any]) -> dict[str, Any]:
        leaks = has_forbidden_outcome_fields(observation)
        pit = pit_feature_violations(observation)
        session = session_from_context(observation)
        volatility = _vol_bucket(observation)
        trend = _trend(observation)
        liquidity = _liquidity(observation)
        spread_state = _spread_state(observation)
        regime = _regime(session, volatility, trend, spread_state)

        reasons: list[str] = []
        limitations: list[str] = ["NOT_A_WIN_PROBABILITY", "NO_OUTCOME_ACCESS", "DETERMINISTIC_V1"]
        if leaks:
            reasons.append("OUTCOME_FIELD_PRESENT_IGNORED")
            limitations.append("OUTCOME_FIELDS_STRIPPED_FROM_CONTEXT")
        if pit:
            reasons.extend(pit[:6])
            limitations.append("POINT_IN_TIME_VIOLATION")

        dq = observation.get("data_quality") or {}
        quote_q = str(dq.get("quote_quality") or "").upper()
        market_data_health = "OK"
        if quote_q in {"", "QUOTE_UNAVAILABLE", "QUOTE_MISSING", "NONE"}:
            market_data_health = "DEGRADED"
            reasons.append("QUOTE_QUALITY_INCOMPLETE")
        elif quote_q in {"QUOTE_STALE", "QUOTE_FUTURE_REJECTED"}:
            market_data_health = "DEGRADED"
            reasons.append(quote_q)

        known = sum(
            1
            for x in (session, volatility, trend, liquidity, spread_state)
            if x != "UNKNOWN"
        )
        confidence = round(known / 5.0, 4)
        if confidence < THRESHOLDS["context_confidence_unknown_below"]:
            reasons.append("CONTEXT_UNKNOWN")

        setup = observation.get("economic_setup") or {}
        symbol = str(setup.get("symbol") or (observation.get("market_context") or {}).get("symbol") or "")
        currency_thesis = f"{symbol}_DIRECTIONAL_CONTEXT" if symbol else "UNKNOWN"
        evidence_refs = [
            f"observation:{observation.get('observation_id')}",
            f"setup:{setup.get('economic_setup_id')}",
            f"bundle:{AGENT_BUNDLE_VERSION}",
        ]

        body: dict[str, Any] = {
            "schema_version": CONTEXT_SCHEMA_VERSION,
            "context_assessment_id": new_id("CTX"),
            "observation_id": observation.get("observation_id"),
            "economic_setup_id": setup.get("economic_setup_id"),
            "agent_id": AGENT_ID,
            "agent_version": AGENT_VERSION,
            "agent_bundle_version": AGENT_BUNDLE_VERSION,
            "created_at_utc": utc_now(),
            "session": session,
            "volatility": volatility,
            "trend": trend,
            "liquidity": liquidity,
            "spread_state": spread_state,
            "regime": regime,
            "currency_thesis": currency_thesis,
            "correlation_context": {"status": "UNAVAILABLE_V1"},
            "portfolio_context": observation.get("portfolio_context") or {},
            "market_data_health": market_data_health,
            "context_confidence": confidence,
            "evidence_refs": evidence_refs,
            "reason_codes": reasons or ["CONTEXT_ASSESSED"],
            "limitations": limitations,
            "point_in_time_violations": pit,
            "outcome_access_count": 0,
            "research_only": True,
        }
        body["feature_schema_hash"] = content_hash(
            {
                "session": session,
                "volatility": volatility,
                "trend": trend,
                "liquidity": liquidity,
                "spread_state": spread_state,
                "regime": regime,
            }
        )
        body["input_hash"] = content_hash(
            {
                "observation_id": observation.get("observation_id"),
                "decision_cutoff_utc": observation.get("decision_cutoff_utc"),
                "features": observation.get("features") or {},
                "market_context": observation.get("market_context") or {},
                "data_quality": observation.get("data_quality") or {},
            }
        )
        body["output_hash"] = content_hash({k: v for k, v in body.items() if k != "output_hash"})
        return body
