"""Minimal diagnostic episodic memory — no decision/shadow influence."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _h(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def encode_episode(
    *,
    context: dict[str, Any],
    narrative: dict[str, Any],
    hypotheses: list[dict[str, Any]],
) -> dict[str, Any]:
    m15 = (context.get("timeframes") or {}).get("M15") or {}
    encoding = {
        "structure_template": {
            "m15_external": m15.get("external_direction"),
            "m15_internal": m15.get("internal_direction"),
            "h1_external": ((context.get("timeframes") or {}).get("H1") or {}).get("external_direction"),
        },
        "liquidity_path": {
            "asymmetry": ((context.get("liquidity") or {}).get("paths") or [{}])[0].get("asymmetry"),
            "n_nodes": (context.get("liquidity") or {}).get("n_nodes"),
        },
        "zone_lifecycle": {
            "n_zones": (context.get("zones") or {}).get("n_zones"),
            "n_armed": len((context.get("zones") or {}).get("armed_ids") or []),
        },
        "session": "UNKNOWN",
        "volatility": "FROM_CONTEXT_UNAVAILABLE",
        "event_risk": context.get("event_risk_state"),
    }
    episode = {
        "episode_id": _h({"c": context.get("context_hash"), "n": narrative.get("narrative_hash")})[:24],
        "symbol": context.get("symbol"),
        "available_at": narrative.get("available_at"),
        "encoding": encoding,
        "narrative_id": narrative.get("narrative_id"),
        "hypothesis_ids": [h["hypothesis_id"] for h in hypotheses],
        "outcome_labels_separated": True,
        "outcome_labels": None,  # never attached for decision use
        "influences_decisions": False,
        "influences_family_shadow": False,
    }
    episode["episode_hash"] = _h(episode)
    return episode


def retrieve_similar(
    query: dict[str, Any], catalog: list[dict[str, Any]], *, top_k: int = 5
) -> list[dict[str, Any]]:
    """Diagnostic retrieval by exact structure_template match then partial overlap."""
    q = (query.get("encoding") or {}).get("structure_template") or {}
    scored = []
    for ep in catalog:
        enc = (ep.get("encoding") or {}).get("structure_template") or {}
        score = 0
        for k in ("m15_external", "m15_internal", "h1_external"):
            if q.get(k) and q.get(k) == enc.get(k):
                score += 1
        scored.append({"episode_id": ep["episode_id"], "score": score, "available_at": ep.get("available_at")})
    scored.sort(key=lambda x: (-x["score"], x["available_at"] or ""))
    return scored[:top_k]


def run_episodic_runtime(
    *,
    context: dict[str, Any],
    narrative: dict[str, Any],
    hypotheses: list[dict[str, Any]],
    prior_episodes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    episode = encode_episode(context=context, narrative=narrative, hypotheses=hypotheses)
    catalog = list(prior_episodes or []) + [episode]
    retrieval = retrieve_similar(episode, [e for e in catalog if e["episode_id"] != episode["episode_id"]] or catalog)
    return {
        "episode": episode,
        "index_keys": ["structure_template", "liquidity_path", "zone_lifecycle", "event_risk"],
        "retrieval": retrieval,
        "policy_influence": False,
        "shadow_influence": False,
    }
