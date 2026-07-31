"""Frozen mechanism-based strategy assessment profiles — research-only, no outcome mining."""

from __future__ import annotations

from typing import Any, Callable

from intelligence_maxxxing.domain_packs.trading.strategy_assessment_validate_v1 import (
    STRATEGY_ASSESSMENT_SCHEMA_VERSION,
    extract_available_at_map,
    extract_factor_states,
)

PROFILE_VERSION = "1.0.0"
PROFILE_FROZEN_AT_UTC = "2026-07-31T00:00:00Z"

AVAILABLE_STATUSES = frozenset(
    {"AVAILABLE_HIGH", "AVAILABLE_MEDIUM", "AVAILABLE_LOW"}
)
BREAKOUT_SESSIONS = frozenset({"LONDON", "NEW_YORK", "OVERLAP"})


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
    cost_threshold: float,
    cost_critical: bool = True,
    reject_on_high_cost: bool = True,
    reject_on_unknown_cost: bool = False,
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
    if commission is None and cost_critical:
        if reject_on_unknown_cost:
            return _reject(
                reason_codes=["REJECT_COST_UNKNOWN"],
                request=request,
                factor_contributions={"commission_r": None},
            )
        return _abstain(
            reason_codes=["ABSTAIN_COST_UNKNOWN"],
            request=request,
            factor_contributions={"commission_r": None},
        )
    if commission is not None and commission > cost_threshold:
        if reject_on_high_cost:
            return _reject(
                reason_codes=["UNECONOMIC_COST_BURDEN", f"COST:{round(commission, 4)}"],
                request=request,
                factor_contributions={"commission_r": commission, "threshold": cost_threshold},
                confidence=0.35,
            )
        return _abstain(
            reason_codes=["ABSTAIN_UNECONOMIC_COST", f"COST:{round(commission, 4)}"],
            request=request,
            factor_contributions={"commission_r": commission, "threshold": cost_threshold},
        )
    return None


def _assess_london_ny_breakout(request: dict[str, Any]) -> dict[str, Any]:
    required = ["session_context", "geometry_valid", "cost_burden"]
    gate = _shared_geometry_cost_gate(
        request,
        required_factors=required,
        cost_threshold=0.10,
        cost_critical=True,
        reject_on_high_cost=True,
        reject_on_unknown_cost=False,
    )
    if gate is not None:
        return gate

    tv = request.get("trader_view") or {}
    factors = _factor_map(tv)
    session = _session_label(factors)
    commission = _commission_r(request, factors)

    if session is None:
        return _abstain(
            reason_codes=["ABSTAIN_SESSION_UNAVAILABLE"],
            request=request,
            factor_contributions={"session": None},
        )
    if session not in BREAKOUT_SESSIONS:
        return _reject(
            reason_codes=["REJECT_SESSION_NOT_BREAKOUT", f"SESSION:{session}"],
            request=request,
            factor_contributions={"session": session},
            confidence=0.40,
        )
    return _take(
        reason_codes=["TAKE_BREAKOUT_SESSION", f"SESSION:{session}", f"COST:{round(commission or 0, 4)}"],
        request=request,
        evidence_for=[f"session={session}", "geometry_valid=true"],
        factor_contributions={"session": session, "commission_r": commission},
        confidence=0.78,
    )


def _assess_session_mean_reversion(request: dict[str, Any]) -> dict[str, Any]:
    required = ["session_context", "geometry_valid", "cost_burden"]
    gate = _shared_geometry_cost_gate(
        request,
        required_factors=required,
        cost_threshold=0.12,
        cost_critical=True,
        reject_on_high_cost=True,
    )
    if gate is not None:
        return gate

    tv = request.get("trader_view") or {}
    factors = _factor_map(tv)
    session_factor = factors.get("session_context")
    if not _is_available(session_factor):
        return _abstain(
            reason_codes=["ABSTAIN_SESSION_UNAVAILABLE"],
            request=request,
        )
    commission = _commission_r(request, factors)
    return _take(
        reason_codes=["TAKE_SESSION_MEAN_REVERSION", f"COST:{round(commission or 0, 4)}"],
        request=request,
        evidence_for=["session_available", "geometry_valid=true"],
        factor_contributions={"session": _session_label(factors), "commission_r": commission},
        confidence=0.72,
    )


def _assess_s13_core(request: dict[str, Any]) -> dict[str, Any]:
    required = ["geometry_valid", "cost_burden"]
    gate = _shared_geometry_cost_gate(
        request,
        required_factors=required,
        cost_threshold=0.15,
        cost_critical=True,
        reject_on_high_cost=True,
    )
    if gate is not None:
        return gate
    commission = _commission_r(request, _factor_map(request.get("trader_view") or {}))
    return _take(
        reason_codes=["TAKE_S13_CORE", f"COST:{round(commission or 0, 4)}"],
        request=request,
        evidence_for=["geometry_valid=true"],
        factor_contributions={"commission_r": commission},
        confidence=0.70,
    )


def _assess_cost_capped(
    request: dict[str, Any],
    *,
    strategy_label: str,
    cost_threshold: float,
    required_factors: list[str] | None = None,
) -> dict[str, Any]:
    required = required_factors or ["geometry_valid", "cost_burden"]
    gate = _shared_geometry_cost_gate(
        request,
        required_factors=required,
        cost_threshold=cost_threshold,
        cost_critical=True,
        reject_on_high_cost=True,
    )
    if gate is not None:
        return gate
    commission = _commission_r(request, _factor_map(request.get("trader_view") or {}))
    return _take(
        reason_codes=[f"TAKE_{strategy_label}", f"COST:{round(commission or 0, 4)}"],
        request=request,
        evidence_for=["geometry_valid=true"],
        factor_contributions={"commission_r": commission},
        confidence=0.68,
    )


PROFILE_REGISTRY: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "LONDON_NY_BREAKOUT": _assess_london_ny_breakout,
    "SESSION_MEAN_REVERSION": _assess_session_mean_reversion,
    "S13_CORE": _assess_s13_core,
    "S14_LIQUIDITY_SWEEP": lambda r: _assess_cost_capped(r, strategy_label="S14_LIQUIDITY_SWEEP", cost_threshold=0.12),
    "HTF_PULLBACK": lambda r: _assess_cost_capped(r, strategy_label="HTF_PULLBACK", cost_threshold=0.12),
    "STRICT_DISPLACEMENT_FVG_RETEST": lambda r: _assess_cost_capped(
        r, strategy_label="STRICT_DISPLACEMENT_FVG_RETEST", cost_threshold=0.12
    ),
    "FALSE_BREAK_REVERSAL_LIQUIDITY_TRAP": lambda r: _assess_cost_capped(
        r, strategy_label="FALSE_BREAK_REVERSAL_LIQUIDITY_TRAP", cost_threshold=0.12
    ),
}


def assess_strategy_request(request: dict[str, Any]) -> dict[str, Any]:
    """Evaluate strategy request using frozen mechanism profiles — never mutates setup prices."""
    strategy = request.get("strategy") or {}
    strategy_id = str(strategy.get("strategy_id") or "")
    assessor = PROFILE_REGISTRY.get(strategy_id)
    if assessor is None:
        return _abstain(
            reason_codes=["ABSTAIN_UNKNOWN_STRATEGY", f"STRATEGY:{strategy_id}"],
            request=request,
        )
    return assessor(request)
