"""Frozen rich PIT factor strategy assessment profiles v2 — research-only, no outcome mining."""

from __future__ import annotations

from typing import Any, Callable

from intelligence_maxxxing.domain_packs.trading.strategy_assessment_validate_v1 import (
    STRATEGY_ASSESSMENT_SCHEMA_VERSION,
    extract_available_at_map,
    extract_factor_states,
)

PROFILE_VERSION = "2.0.0"
PROFILE_FROZEN_AT_UTC = "2026-07-31T22:00:00Z"

AVAILABLE_STATUSES = frozenset(
    {"AVAILABLE_HIGH", "AVAILABLE_MEDIUM", "AVAILABLE_LOW"}
)
BREAKOUT_SESSIONS = frozenset({"LONDON", "NEW_YORK", "OVERLAP"})

V2_BASE_REQUIRED = [
    "session_context",
    "geometry_valid",
    "cost_burden",
    "atr_m5",
    "volatility_percentile",
    "h1_trend_alignment",
    "stop_distance_atr",
]


def _factor_map(trader_view: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("factor_id")): row
        for row in extract_factor_states(trader_view)
        if row.get("factor_id")
    }


def _factor_status(factor: dict[str, Any] | None) -> str:
    if not factor:
        return "UNKNOWN"
    return str(factor.get("status") or factor.get("state") or "UNKNOWN")


def _factor_value(factor: dict[str, Any] | None) -> Any:
    if not factor:
        return None
    return factor.get("value")


def _is_unknown(factor: dict[str, Any] | None) -> bool:
    return _factor_status(factor) == "UNKNOWN"


def _is_available(factor: dict[str, Any] | None) -> bool:
    return _factor_status(factor) in AVAILABLE_STATUSES


def _geometry_valid(setup: dict[str, Any], factors: dict[str, dict[str, Any]]) -> bool:
    entry = setup.get("entry")
    stop = setup.get("stop")
    if entry is None or stop is None:
        return False
    try:
        if float(entry) == float(stop):
            return False
    except (TypeError, ValueError):
        return False
    geom_factor = factors.get("geometry_valid")
    if geom_factor is not None and _is_available(geom_factor):
        val = _factor_value(geom_factor)
        if isinstance(val, bool):
            return val
        if isinstance(val, dict) and "valid" in val:
            return bool(val["valid"])
    return True


def _commission_r(request: dict[str, Any], factors: dict[str, dict[str, Any]]) -> float | None:
    costs = request.get("costs") or {}
    raw = costs.get("commission_r")
    if raw is not None:
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None
    burden = factors.get("cost_burden")
    if burden is not None and _is_available(burden):
        val = _factor_value(burden)
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, dict):
            for key in ("commission_r", "burden_r", "value"):
                if key in val and val[key] is not None:
                    try:
                        return float(val[key])
                    except (TypeError, ValueError):
                        pass
    return None


def _session_label(factors: dict[str, dict[str, Any]]) -> str | None:
    session = factors.get("session_context")
    if session is None or not _is_available(session):
        return None
    val = _factor_value(session)
    if isinstance(val, str):
        return val.upper()
    if isinstance(val, dict):
        for key in ("session", "label", "value"):
            if val.get(key):
                return str(val[key]).upper()
    return None


def _float_factor(factors: dict[str, dict[str, Any]], factor_id: str) -> float | None:
    factor = factors.get(factor_id)
    if factor is None or not _is_available(factor):
        return None
    val = _factor_value(factor)
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, dict):
        for key in ("value", factor_id):
            if key in val and val[key] is not None:
                try:
                    return float(val[key])
                except (TypeError, ValueError):
                    pass
    return None


def _alignment_label(factors: dict[str, dict[str, Any]]) -> str | None:
    factor = factors.get("h1_trend_alignment")
    if factor is None or not _is_available(factor):
        return None
    val = _factor_value(factor)
    if isinstance(val, str):
        return val.upper()
    if isinstance(val, dict):
        for key in ("alignment", "label", "value"):
            if val.get(key):
                return str(val[key]).upper()
    return None


def _required_unknown(factors: dict[str, dict[str, Any]], required: list[str]) -> list[str]:
    unknown: list[str] = []
    for fid in required:
        if _is_unknown(factors.get(fid)):
            unknown.append(fid)
    return unknown


def _abstain(
    *,
    reason_codes: list[str],
    request: dict[str, Any],
    evidence_for: list[str] | None = None,
    evidence_against: list[str] | None = None,
    factor_contributions: dict[str, Any] | None = None,
    confidence: float | None = None,
) -> dict[str, Any]:
    return _result(
        decision="ABSTAIN",
        reason_codes=reason_codes,
        request=request,
        evidence_for=evidence_for or [],
        evidence_against=evidence_against or [],
        factor_contributions=factor_contributions or {},
        confidence=confidence,
        eligible=False,
    )


def _reject(
    *,
    reason_codes: list[str],
    request: dict[str, Any],
    evidence_for: list[str] | None = None,
    evidence_against: list[str] | None = None,
    factor_contributions: dict[str, Any] | None = None,
    confidence: float | None = None,
) -> dict[str, Any]:
    return _result(
        decision="REJECT",
        reason_codes=reason_codes,
        request=request,
        evidence_for=evidence_for or [],
        evidence_against=evidence_against or [],
        factor_contributions=factor_contributions or {},
        confidence=confidence,
        eligible=False,
    )


def _take(
    *,
    reason_codes: list[str],
    request: dict[str, Any],
    evidence_for: list[str] | None = None,
    evidence_against: list[str] | None = None,
    factor_contributions: dict[str, Any] | None = None,
    confidence: float | None = None,
) -> dict[str, Any]:
    return _result(
        decision="TAKE",
        reason_codes=reason_codes,
        request=request,
        evidence_for=evidence_for or [],
        evidence_against=evidence_against or [],
        factor_contributions=factor_contributions or {},
        confidence=confidence,
        eligible=True,
    )


def _result(
    *,
    decision: str,
    reason_codes: list[str],
    request: dict[str, Any],
    evidence_for: list[str],
    evidence_against: list[str],
    factor_contributions: dict[str, Any],
    confidence: float | None,
    eligible: bool,
) -> dict[str, Any]:
    strategy = request.get("strategy") or {}
    return {
        "schema_version": STRATEGY_ASSESSMENT_SCHEMA_VERSION,
        "decision": decision,
        "confidence": confidence,
        "reason_codes": reason_codes,
        "evidence_for": evidence_for,
        "evidence_against": evidence_against,
        "factor_contributions": factor_contributions,
        "factor_available_at_preserved": extract_available_at_map(request),
        "eligible_for_economic_evaluation": eligible and decision == "TAKE",
        "profile_version": PROFILE_VERSION,
        "profile_frozen_at_utc": PROFILE_FROZEN_AT_UTC,
        "strategy_id": strategy.get("strategy_id"),
        "family": strategy.get("family"),
        "research_only": True,
    }


def _shared_geometry_cost_gate(
    request: dict[str, Any],
    *,
    required_factors: list[str],
) -> dict[str, Any] | None:
    """Return early decision if shared gates fail; None if caller should continue."""
    tv = request.get("trader_view") or {}
    setup = request.get("setup") or {}
    factors = _factor_map(tv)

    unknown = _required_unknown(factors, required_factors)
    if unknown:
        return _abstain(
            reason_codes=["ABSTAIN_REQUIRED_FACTOR_UNKNOWN"] + [f"UNKNOWN:{f}" for f in unknown],
            request=request,
            factor_contributions={"unknown_required": unknown},
        )

    if not _geometry_valid(setup, factors):
        return _abstain(
            reason_codes=["ABSTAIN_GEOMETRY_INVALID"],
            request=request,
            factor_contributions={"geometry_valid": False},
        )

    commission = _commission_r(request, factors)
    if commission is not None and commission > 0.12:
        return _reject(
            reason_codes=["UNECONOMIC_COST_BURDEN", f"COST:{round(commission, 4)}"],
            request=request,
            factor_contributions={"commission_r": commission, "threshold": 0.12},
            confidence=0.35,
        )
    return None


def _assess_session_mean_reversion(request: dict[str, Any]) -> dict[str, Any]:
    gate = _shared_geometry_cost_gate(request, required_factors=V2_BASE_REQUIRED)
    if gate is not None:
        return gate

    factors = _factor_map(request.get("trader_view") or {})
    vol_pct = _float_factor(factors, "volatility_percentile")
    alignment = _alignment_label(factors)
    commission = _commission_r(request, factors)

    if vol_pct is not None and vol_pct > 0.90:
        return _reject(
            reason_codes=["REJECT_EXTREME_EXPANSION", f"VOL_PCT:{round(vol_pct, 4)}"],
            request=request,
            factor_contributions={"volatility_percentile": vol_pct},
            confidence=0.42,
        )
    if alignment == "WITH_TRADE":
        return _reject(
            reason_codes=["REJECT_STRONG_TREND_ALIGNMENT", f"ALIGNMENT:{alignment}"],
            request=request,
            factor_contributions={"h1_trend_alignment": alignment},
            confidence=0.45,
        )
    return _take(
        reason_codes=["TAKE_SESSION_MR_CONTEXT", f"COST:{round(commission or 0, 4)}"],
        request=request,
        evidence_for=["geometry_valid=true", "volatility_not_extreme", "trend_not_with_trade"],
        factor_contributions={
            "session": _session_label(factors),
            "volatility_percentile": vol_pct,
            "h1_trend_alignment": alignment,
            "commission_r": commission,
        },
        confidence=0.74,
    )


def _assess_false_break_reversal_liquidity_trap(request: dict[str, Any]) -> dict[str, Any]:
    gate = _shared_geometry_cost_gate(request, required_factors=V2_BASE_REQUIRED)
    if gate is not None:
        return gate

    factors = _factor_map(request.get("trader_view") or {})
    session = _session_label(factors)
    stop_dist = _float_factor(factors, "stop_distance_atr")
    commission = _commission_r(request, factors)

    if session is None or session not in BREAKOUT_SESSIONS:
        return _reject(
            reason_codes=["REJECT_SESSION_NOT_BREAKOUT", f"SESSION:{session}"],
            request=request,
            factor_contributions={"session": session},
            confidence=0.40,
        )
    if stop_dist is not None and stop_dist > 2.5:
        return _reject(
            reason_codes=["REJECT_STOP_TOO_WIDE_VS_ATR", f"STOP_ATR:{round(stop_dist, 4)}"],
            request=request,
            factor_contributions={"stop_distance_atr": stop_dist},
            confidence=0.43,
        )
    return _take(
        reason_codes=["TAKE_FALSE_BREAK_CONTEXT", f"SESSION:{session}", f"COST:{round(commission or 0, 4)}"],
        request=request,
        evidence_for=[f"session={session}", "stop_within_atr_budget"],
        factor_contributions={
            "session": session,
            "stop_distance_atr": stop_dist,
            "commission_r": commission,
        },
        confidence=0.76,
    )


def _assess_htf_pullback(request: dict[str, Any]) -> dict[str, Any]:
    gate = _shared_geometry_cost_gate(request, required_factors=V2_BASE_REQUIRED)
    if gate is not None:
        return gate

    factors = _factor_map(request.get("trader_view") or {})
    alignment = _alignment_label(factors)
    commission = _commission_r(request, factors)

    if alignment == "AGAINST_TRADE":
        return _reject(
            reason_codes=["REJECT_HTF_AGAINST", f"ALIGNMENT:{alignment}"],
            request=request,
            factor_contributions={"h1_trend_alignment": alignment},
            confidence=0.44,
        )
    return _take(
        reason_codes=["TAKE_HTF_PULLBACK_ALIGNED", f"ALIGNMENT:{alignment}", f"COST:{round(commission or 0, 4)}"],
        request=request,
        evidence_for=[f"h1_trend_alignment={alignment}"],
        factor_contributions={"h1_trend_alignment": alignment, "commission_r": commission},
        confidence=0.73,
    )


def _assess_strict_displacement_fvg_retest(request: dict[str, Any]) -> dict[str, Any]:
    required = V2_BASE_REQUIRED + ["displacement_atr"]
    gate = _shared_geometry_cost_gate(request, required_factors=required)
    if gate is not None:
        return gate

    factors = _factor_map(request.get("trader_view") or {})
    displacement = factors.get("displacement_atr")
    if _is_unknown(displacement):
        return _abstain(
            reason_codes=["ABSTAIN_REQUIRED_FACTOR_UNKNOWN", "UNKNOWN:displacement_atr"],
            request=request,
            factor_contributions={"unknown_required": ["displacement_atr"]},
        )

    disp_atr = _float_factor(factors, "displacement_atr")
    commission = _commission_r(request, factors)

    if disp_atr is None:
        return _abstain(
            reason_codes=["ABSTAIN_REQUIRED_FACTOR_UNKNOWN", "UNKNOWN:displacement_atr"],
            request=request,
            factor_contributions={"displacement_atr": None},
        )
    if disp_atr < 0.8:
        return _reject(
            reason_codes=["REJECT_WEAK_DISPLACEMENT", f"DISP_ATR:{round(disp_atr, 4)}"],
            request=request,
            factor_contributions={"displacement_atr": disp_atr},
            confidence=0.41,
        )
    return _take(
        reason_codes=["TAKE_STRICT_FVG_DISPLACEMENT", f"DISP_ATR:{round(disp_atr, 4)}", f"COST:{round(commission or 0, 4)}"],
        request=request,
        evidence_for=["displacement_atr>=0.8"],
        factor_contributions={"displacement_atr": disp_atr, "commission_r": commission},
        confidence=0.75,
    )


PROFILE_REGISTRY: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "SESSION_MEAN_REVERSION": _assess_session_mean_reversion,
    "FALSE_BREAK_REVERSAL_LIQUIDITY_TRAP": _assess_false_break_reversal_liquidity_trap,
    "HTF_PULLBACK": _assess_htf_pullback,
    "STRICT_DISPLACEMENT_FVG_RETEST": _assess_strict_displacement_fvg_retest,
}


def assess_strategy_request_v2(request: dict[str, Any]) -> dict[str, Any]:
    """Evaluate strategy request using frozen rich PIT factor profiles v2 — never mutates setup prices."""
    strategy = request.get("strategy") or {}
    strategy_id = str(strategy.get("strategy_id") or "")
    assessor = PROFILE_REGISTRY.get(strategy_id)
    if assessor is None:
        return _abstain(
            reason_codes=["ABSTAIN_UNKNOWN_STRATEGY", f"STRATEGY:{strategy_id}"],
            request=request,
        )
    return assessor(request)
