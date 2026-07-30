"""IM CMSR decision policy — deterministic, frozen, research-only."""

from __future__ import annotations

from typing import Any

from intelligence_maxxxing.domain_packs.trading.cmsr_validate_v1 import (
    CMSR_POLICY_FROZEN_AT_UTC,
    CMSR_POLICY_ID,
    CMSR_POLICY_VERSION,
    CMSR_RULESET_HASH,
    extract_available_at_map,
)


def _factor_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("factor_id")): row
        for row in (snapshot.get("factors") or [])
        if isinstance(row, dict) and row.get("factor_id")
    }


def _list_lines(factor: dict[str, Any] | None) -> list[str]:
    if not factor:
        return []
    value = factor.get("value")
    if isinstance(value, list):
        return [str(v) for v in value[:12]]
    if isinstance(value, dict):
        lines = value.get("lines") or value.get("items") or value.get("evidence")
        if isinstance(lines, list):
            return [str(v) for v in lines[:12]]
    return []


def _uncertainty_score(factor: dict[str, Any] | None) -> float | None:
    if not factor:
        return None
    value = factor.get("value")
    if isinstance(value, dict):
        for key in ("score", "uncertainty", "level"):
            raw = value.get(key)
            if isinstance(raw, (int, float)):
                return max(0.0, min(1.0, float(raw)))
    conf = factor.get("confidence")
    if isinstance(conf, (int, float)):
        return max(0.0, min(1.0, 1.0 - float(conf)))
    return None


def assess_cmsr_request(request: dict[str, Any]) -> dict[str, Any]:
    """Evaluate CMSR request using epistemic factors — never leaks outcomes."""
    snap = request.get("trader_view_snapshot") or {}
    factors = _factor_map(snap)
    readiness = snap.get("readiness") or {}

    evidence_for = _list_lines(factors.get("evidence_for"))
    evidence_against = _list_lines(factors.get("evidence_against"))
    uncertainty = _uncertainty_score(factors.get("uncertainty"))

    reason_codes: list[str] = []
    if evidence_for:
        reason_codes.append(f"EVIDENCE_FOR:{len(evidence_for)}")
    if evidence_against:
        reason_codes.append(f"EVIDENCE_AGAINST:{len(evidence_against)}")
    if uncertainty is not None:
        reason_codes.append(f"UNCERTAINTY:{round(uncertainty, 4)}")

    if readiness.get("readiness") == "BLOCKED_CRITICAL_FACTOR":
        return _result(
            decision="ABSTAIN",
            confidence=None,
            reason_codes=reason_codes + ["BLOCKED_CRITICAL_FACTOR"],
            request=request,
            eligible=False,
        )
    if not readiness.get("economic_take_permitted", False):
        return _result(
            decision="ABSTAIN",
            confidence=None,
            reason_codes=reason_codes + ["ECONOMIC_TAKE_NOT_PERMITTED"],
            request=request,
            eligible=False,
        )

    if uncertainty is not None and uncertainty >= 0.75:
        return _result(
            decision="ABSTAIN",
            confidence=None,
            reason_codes=reason_codes + ["UNCERTAINTY_TOO_HIGH"],
            request=request,
            eligible=False,
        )

    cross = factors.get("cross_market_confirmation") or {}
    cross_state = str(cross.get("state") or "")
    if cross_state.startswith("AVAILABLE"):
        val = cross.get("value")
        if isinstance(val, dict) and val.get("aligned") is False:
            return _result(
                decision="REJECT",
                confidence=0.35,
                reason_codes=reason_codes + ["CROSS_MARKET_MISALIGNED"],
                request=request,
                eligible=False,
            )
        if isinstance(val, dict) and val.get("reduce_confidence") is True:
            return _result(
                decision="REDUCE_CONFIDENCE",
                confidence=0.55,
                reason_codes=reason_codes + ["CROSS_MARKET_WEAK"],
                request=request,
                eligible=False,
            )
        if len(evidence_against) > len(evidence_for):
            return _result(
                decision="REDUCE_CONFIDENCE",
                confidence=0.52,
                reason_codes=reason_codes + ["EVIDENCE_AGAINST_DOMINANT"],
                request=request,
                eligible=False,
            )
        return _result(
            decision="TAKE",
            confidence=0.82,
            reason_codes=reason_codes + ["CROSS_MARKET_CONFIRMED"],
            request=request,
            eligible=True,
        )

    regime = factors.get("regime") or {}
    if str(regime.get("state") or "").startswith("AVAILABLE"):
        return _result(
            decision="REDUCE_CONFIDENCE",
            confidence=0.48,
            reason_codes=reason_codes + ["REGIME_ONLY_CONTEXT"],
            request=request,
            eligible=False,
        )

    return _result(
        decision="ABSTAIN",
        confidence=None,
        reason_codes=reason_codes + ["INSUFFICIENT_CONTEXT"],
        request=request,
        eligible=False,
    )


def _result(
    *,
    decision: str,
    confidence: float | None,
    reason_codes: list[str],
    request: dict[str, Any],
    eligible: bool,
) -> dict[str, Any]:
    return {
        "decision": decision,
        "confidence": confidence,
        "reason_codes": reason_codes,
        "factor_available_at_preserved": extract_available_at_map(request),
        "eligible_for_economic_evaluation": eligible and decision == "TAKE",
        "policy_id": CMSR_POLICY_ID,
        "policy_version": CMSR_POLICY_VERSION,
        "policy_frozen_at_utc": CMSR_POLICY_FROZEN_AT_UTC,
        "ruleset_hash": CMSR_RULESET_HASH,
    }
