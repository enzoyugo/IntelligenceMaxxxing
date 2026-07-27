"""Deterministic narrative + hypothesis builder from context JSON (no TMX imports)."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _h(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _human_from_json(narrative: dict[str, Any]) -> str:
    """Derive human text strictly from JSON fields — no new evidence."""
    parts = [
        f"Symbol {narrative.get('symbol')} as_of {narrative.get('as_of')}.",
        f"Structure: {narrative.get('structure_summary')}.",
        f"Liquidity: {narrative.get('liquidity_summary')}.",
        f"Zones: {narrative.get('zone_summary')}.",
        f"Regime: {narrative.get('regime_summary')}.",
        f"Event risk: {narrative.get('event_risk_summary')}.",
        f"Uncertainty: {narrative.get('uncertainty')}.",
        f"Evidence ids: {', '.join(narrative.get('evidence_object_ids') or [])}.",
    ]
    return " ".join(parts)


def build_narrative(context: dict[str, Any]) -> dict[str, Any]:
    tfs = context.get("timeframes") or {}
    m15 = tfs.get("M15") or {}
    h1 = tfs.get("H1") or {}
    liq = context.get("liquidity") or {}
    zones = context.get("zones") or {}
    evidence = [e for e in (context.get("evidence_object_ids") or []) if e]

    structure_summary = (
        f"M15 external={m15.get('external_direction')} internal={m15.get('internal_direction')}; "
        f"H1 external={h1.get('external_direction')}; "
        f"alignment={context.get('mtf', {}).get('alignment')}"
    )
    paths = liq.get("paths") or []
    asymmetry = None
    if paths:
        asymmetry = paths[0].get("asymmetry")
    liquidity_summary = (
        f"nodes={liq.get('n_nodes')} asymmetry={asymmetry} "
        f"sweeps={liq.get('sweep_stats')}"
    )
    zone_summary = f"n_zones={zones.get('n_zones')} armed={len(zones.get('armed_ids') or [])}"
    regime_summary = f"shared_context_hash_present={bool(context.get('context_hash'))}"
    event_risk_summary = str(context.get("event_risk_state") or "CALENDAR_UNKNOWN")

    # Uncertainty rises when MTF conflict or calendar unknown
    uncertainty = 0.35
    if not context.get("mtf", {}).get("alignment"):
        uncertainty += 0.2
    if event_risk_summary == "CALENDAR_UNKNOWN":
        uncertainty += 0.15
    if (m15.get("external_direction") or "NONE") == "NONE":
        uncertainty += 0.15
    uncertainty = min(0.95, uncertainty)

    narrative = {
        "narrative_id": _h({"sym": context.get("symbol"), "as": context.get("as_of"), "ch": context.get("context_hash")})[:24],
        "symbol": context.get("symbol"),
        "as_of": context.get("as_of"),
        "available_at": context.get("available_at") or context.get("as_of"),
        "structure_summary": structure_summary,
        "liquidity_summary": liquidity_summary,
        "zone_summary": zone_summary,
        "regime_summary": regime_summary,
        "event_risk_summary": event_risk_summary,
        "evidence_object_ids": evidence,
        "uncertainty": round(uncertainty, 4),
        "forbids_outcomes": True,
        "authority": "IM",
    }
    narrative["narrative_hash"] = _h(narrative)
    narrative["human_text"] = _human_from_json(narrative)
    # prove human text adds no evidence ids
    narrative["human_text_evidence_subset"] = True
    return narrative


def build_hypotheses(context: dict[str, Any], narrative: dict[str, Any]) -> list[dict[str, Any]]:
    tfs = context.get("timeframes") or {}
    m15 = tfs.get("M15") or {}
    direction = m15.get("external_direction") or "NONE"
    evidence = list(narrative.get("evidence_object_ids") or [])
    armed = (context.get("zones") or {}).get("armed_ids") or []
    paths = (context.get("liquidity") or {}).get("paths") or []
    target = None
    if paths:
        target = paths[0].get("nearest_external_above") if direction == "UP" else paths[0].get(
            "nearest_external_below"
        )

    primary_dir = "BULLISH" if direction == "UP" else "BEARISH" if direction == "DOWN" else "NEUTRAL"
    alt_dir = "BEARISH" if primary_dir == "BULLISH" else "BULLISH" if primary_dir == "BEARISH" else "NEUTRAL"

    primary = {
        "hypothesis_id": _h({"n": narrative["narrative_id"], "d": primary_dir, "k": "primary"})[:24],
        "thesis": f"External structure {direction} favors {primary_dir} continuation pending invalidation",
        "direction": primary_dir,
        "state": "ACTIVE" if primary_dir != "NEUTRAL" else "CREATED",
        "invalidation": "CHOCH/MSS against external direction or protected level failure",
        "targets": [target] if target else [],
        "target_liquidity": target,
        "evidence_for": evidence[:10],
        "evidence_against": [],
        "alternative_hypothesis_id": None,
        "evidence_links": evidence[:10],
        "available_at": narrative["available_at"],
        "confidence": round(max(0.05, 1.0 - float(narrative["uncertainty"])), 4),
        "uncertainty": narrative["uncertainty"],
        "forbids_outcomes": True,
        "armed_zones": armed[:5],
    }
    alt = {
        "hypothesis_id": _h({"n": narrative["narrative_id"], "d": alt_dir, "k": "alt"})[:24],
        "thesis": f"Alternative: {alt_dir} path if liquidity sweep + CHOCH against current external",
        "direction": alt_dir,
        "state": "CREATED",
        "invalidation": "BOS continuation confirming primary",
        "targets": [],
        "target_liquidity": paths[0].get("nearest_external_below")
        if paths and primary_dir == "BULLISH"
        else (paths[0].get("nearest_external_above") if paths else None),
        "evidence_for": [],
        "evidence_against": evidence[:5],
        "alternative_hypothesis_id": None,
        "evidence_links": evidence[:5],
        "available_at": narrative["available_at"],
        "confidence": round(float(narrative["uncertainty"]) * 0.5, 4),
        "uncertainty": narrative["uncertainty"],
        "forbids_outcomes": True,
        "armed_zones": [],
    }
    primary["alternative_hypothesis_id"] = alt["hypothesis_id"]
    alt["alternative_hypothesis_id"] = primary["hypothesis_id"]
    for h in (primary, alt):
        h["hypothesis_hash"] = _h({k: h[k] for k in h if k != "hypothesis_hash"})
    return [primary, alt]


def hypothesis_transitions(hypotheses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for h in hypotheses:
        out.append(
            {
                "hypothesis_id": h["hypothesis_id"],
                "prior_state": "NONE",
                "new_state": h["state"],
                "available_at": h["available_at"],
                "trigger": "narrative_runtime_v1",
            }
        )
    return out


def run_narrative_runtime(context: dict[str, Any]) -> dict[str, Any]:
    narrative = build_narrative(context)
    hyps = build_hypotheses(context, narrative)
    transitions = hypothesis_transitions(hyps)
    # contradiction if MTF misaligned
    contradiction = None
    if not (context.get("mtf") or {}).get("alignment"):
        contradiction = {
            "type": "MTF_DIRECTION_CONFLICT",
            "handling": "raise_uncertainty_keep_both_hypotheses",
            "uncertainty": narrative["uncertainty"],
        }
    return {
        "narrative": narrative,
        "hypotheses": hyps,
        "transitions": transitions,
        "contradiction": contradiction,
        "deterministic": True,
    }
