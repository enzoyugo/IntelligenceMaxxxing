"""HorizonNoiseAgentV1 — observational only; outside frozen M2 decision bundle.

Does not mutate IM_M2_AGENT_BUNDLE@1.0.0 or IM_TRADING_DECISION_POLICY@1.0.0.
Never returns TAKE/SKIP. Never uses outcome.
"""

from __future__ import annotations

from typing import Any

from intelligence_maxxxing.domain_packs.trading.agents._common import (
    content_hash,
    feature_value,
    has_forbidden_outcome_fields,
    new_id,
    utc_now,
)

AGENT_ID = "HorizonNoiseAgentV1"
AGENT_VERSION = "1.0.0"
SCHEMA_VERSION = "im.trading.horizon_noise_assessment.v1"
# Explicitly NOT part of frozen decision bundle mutations.
OUTSIDE_FROZEN_M2_BUNDLE = True


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _from_snapshot(snap: dict[str, Any], *path: str) -> Any:
    cur: Any = snap
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


class HorizonNoiseAgentV1:
    agent_id = AGENT_ID
    agent_version = AGENT_VERSION

    def assess(
        self,
        *,
        observation: dict[str, Any] | None = None,
        pre_decision_horizon_snapshot: dict[str, Any] | None = None,
        context_assessment: dict[str, Any] | None = None,
        anomaly_findings: list[dict[str, Any]] | None = None,
        data_quality: dict[str, Any] | None = None,
        diagnostic_prior_trusted: bool = False,
    ) -> dict[str, Any]:
        observation = observation or {}
        snap = pre_decision_horizon_snapshot or {}
        leaks = has_forbidden_outcome_fields(observation) + has_forbidden_outcome_fields(snap)
        # Strip outcome if present in snap (defensive)
        reason_codes: list[str] = []
        limitations = [
            "NON_AUTHORITATIVE",
            "NO_TAKE_SKIP",
            "NO_OUTCOME_ACCESS",
            "OUTSIDE_FROZEN_M2_DECISION_BUNDLE",
            "DOES_NOT_MUTATE_IM_ADVISORY",
        ]

        if not diagnostic_prior_trusted:
            reason_codes.append("NO_TRUSTED_PRIOR")
            limitations.append("DIAGNOSTIC_PRIOR_N33_NOT_TRUSTED")

        spread_to_stop = _num(
            _from_snapshot(snap, "microstructure", "spread_to_stop_ratio")
            or feature_value(observation, "spread_to_stop_ratio")
        )
        stop_pips = _num(
            _from_snapshot(snap, "geometry", "stop_distance_pips")
            or feature_value(observation, "stop_distance_pips")
        )
        stop_to_atr = _num(
            _from_snapshot(snap, "volatility", "stop_to_atr_m5")
            or feature_value(observation, "stop_to_atr_m5")
        )
        entry_range_to_stop = _num(_from_snapshot(snap, "volatility", "entry_bar_range_to_stop"))
        confirmation = str(
            _from_snapshot(snap, "breakout_quality", "confirmation_status")
            or feature_value(observation, "confirmation_status")
            or "UNKNOWN"
        ).upper()
        htf = str(
            _from_snapshot(snap, "context", "higher_timeframe_alignment")
            or feature_value(observation, "higher_timeframe_alignment")
            or "UNKNOWN"
        ).upper()
        session = str(
            _from_snapshot(snap, "context", "session")
            or feature_value(observation, "session")
            or "UNKNOWN"
        ).upper()
        vol_bucket = str(
            _from_snapshot(snap, "volatility", "volatility_bucket")
            or feature_value(observation, "volatility_bucket")
            or "UNKNOWN"
        ).upper()

        if spread_to_stop is not None and spread_to_stop >= 0.10:
            reason_codes.append("SPREAD_MATERIAL_TO_STOP")
        if stop_pips is not None and stop_pips < 3.0:
            reason_codes.append("STOP_SMALL_ABSOLUTE")
        if stop_to_atr is not None and stop_to_atr < 0.75:
            reason_codes.append("STOP_LOW_RELATIVE_TO_ATR")
        if entry_range_to_stop is not None and entry_range_to_stop >= 1.0:
            reason_codes.append("ENTRY_BAR_LARGE_RELATIVE_TO_STOP")
        if confirmation == "WICK_ONLY":
            reason_codes.append("BREAKOUT_WICK_ONLY")
        elif confirmation == "CONFIRMED":
            reason_codes.append("BREAKOUT_CLOSE_CONFIRMED")
        if str(_from_snapshot(snap, "breakout_quality", "retest_status_at_cutoff") or "NO_RETEST") == "NO_RETEST":
            reason_codes.append("NO_RETEST")
        if htf == "ALIGNED":
            reason_codes.append("HTF_ALIGNED")
        elif htf == "CONFLICT":
            reason_codes.append("HTF_CONFLICT")
        if "TRANSITION" in session:
            reason_codes.append("SESSION_TRANSITION")
        if vol_bucket in {"VERY_LOW", "LOW"} and stop_to_atr is not None and stop_to_atr > 1.5:
            reason_codes.append("VOLATILITY_TOO_LOW")
        if vol_bucket in {"HIGH", "EXTREME"}:
            reason_codes.append("VOLATILITY_TOO_HIGH")

        dq = data_quality or {}
        dq_status = str(
            snap.get("data_quality_status")
            or dq.get("status")
            or dq.get("quote_quality")
            or ""
        ).upper()
        if "PARTIAL" in dq_status or "UNTRUSTED" in dq_status or "INCOMPLETE" in dq_status:
            reason_codes.append("DATA_INCOMPLETE")
        if snap.get("missing_fields"):
            reason_codes.append("DATA_INCOMPLETE")
        if leaks:
            reason_codes.append("OUTCOME_FIELD_PRESENT_IGNORED")
            limitations.append("OUTCOME_FIELDS_IGNORED")

        # Classifications (non-decision)
        if stop_pips is not None and stop_pips < 2.0 and (spread_to_stop or 0) >= 0.15:
            expected_horizon = "ULTRA_SHORT"
            noise = "EXTREME"
        elif stop_pips is not None and stop_pips < 4.0:
            expected_horizon = "SHORT"
            noise = "HIGH" if (spread_to_stop or 0) >= 0.10 or (stop_to_atr or 99) < 0.75 else "MODERATE"
        elif stop_pips is None and stop_to_atr is None:
            expected_horizon = "UNKNOWN"
            noise = "UNKNOWN"
            reason_codes.append("INSUFFICIENT_SAMPLE")
        else:
            expected_horizon = "INTRADAY"
            noise = "MODERATE" if (stop_to_atr or 1) >= 1.0 else "HIGH"

        if confirmation == "CONFIRMED" and htf == "ALIGNED":
            entry_quality = "STRONG"
            breakout_quality = "CONFIRMED"
        elif confirmation == "CONFIRMED":
            entry_quality = "ACCEPTABLE"
            breakout_quality = "CONFIRMED"
        elif confirmation == "WICK_ONLY":
            entry_quality = "WEAK"
            breakout_quality = "WICK_ONLY"
        elif confirmation == "FAILED_AT_CUTOFF":
            entry_quality = "WEAK"
            breakout_quality = "FAILED_AT_CUTOFF"
        elif confirmation == "PARTIAL":
            entry_quality = "UNCONFIRMED"
            breakout_quality = "PARTIAL"
        else:
            entry_quality = "UNKNOWN"
            breakout_quality = "UNKNOWN"

        if stop_pips is not None and stop_pips < 1.5:
            stop_robustness = "EXTREMELY_TIGHT"
        elif stop_pips is not None and stop_pips < 3.0:
            stop_robustness = "TIGHT"
        elif stop_to_atr is not None and stop_to_atr >= 1.0:
            stop_robustness = "ROBUST"
        elif stop_to_atr is not None:
            stop_robustness = "NORMAL"
        else:
            stop_robustness = "UNKNOWN"

        if spread_to_stop is None:
            cost_sensitivity = "UNKNOWN"
        elif spread_to_stop >= 0.30:
            cost_sensitivity = "EXTREME"
        elif spread_to_stop >= 0.15:
            cost_sensitivity = "HIGH"
        elif spread_to_stop >= 0.08:
            cost_sensitivity = "MODERATE"
        else:
            cost_sensitivity = "LOW"

        known = sum(
            1
            for x in (expected_horizon, noise, entry_quality, breakout_quality, stop_robustness, cost_sensitivity)
            if x != "UNKNOWN"
        )
        confidence = round(known / 6.0, 4)

        setup = observation.get("economic_setup") if isinstance(observation.get("economic_setup"), dict) else {}
        economic_setup_id = (
            snap.get("economic_setup_id")
            or setup.get("economic_setup_id")
            or observation.get("economic_setup_id")
        )

        # Context/anomaly refs are informational only
        evidence_refs = [
            f"observation:{observation.get('observation_id')}",
            f"horizon_snapshot:{snap.get('horizon_observation_id')}",
            f"setup:{economic_setup_id}",
        ]
        if isinstance(context_assessment, dict) and context_assessment.get("context_assessment_id"):
            evidence_refs.append(f"context:{context_assessment.get('context_assessment_id')}")
        if anomaly_findings:
            evidence_refs.append(f"anomaly_count:{len(anomaly_findings)}")

        body: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "horizon_assessment_id": new_id("HZN"),
            "economic_setup_id": economic_setup_id,
            "observation_id": observation.get("observation_id"),
            "agent_id": AGENT_ID,
            "agent_version": AGENT_VERSION,
            "outside_frozen_m2_bundle": OUTSIDE_FROZEN_M2_BUNDLE,
            "frozen_policy_untouched": "IM_TRADING_DECISION_POLICY@1.0.0",
            "frozen_bundle_untouched": "IM_M2_AGENT_BUNDLE@1.0.0",
            "created_at": utc_now(),
            "expected_horizon_class": expected_horizon,
            "noise_exposure": noise,
            "entry_quality": entry_quality,
            "breakout_quality": breakout_quality,
            "stop_robustness": stop_robustness,
            "cost_sensitivity": cost_sensitivity,
            "reason_codes": reason_codes or ["HORIZON_ASSESSED"],
            "evidence_refs": evidence_refs,
            "limitations": limitations,
            "confidence": confidence,
            "non_authoritative": True,
            "live_control": False,
            "promotion_eligible": False,
            "mutates_im_advisory": False,
            "decision": None,
            "outcome_access_count": 0,
            "research_only": True,
        }
        body["input_hash"] = content_hash(
            {
                "economic_setup_id": economic_setup_id,
                "observation_id": observation.get("observation_id"),
                "snapshot_output_hash": snap.get("output_hash"),
                "spread_to_stop": spread_to_stop,
                "stop_pips": stop_pips,
                "stop_to_atr": stop_to_atr,
                "confirmation": confirmation,
                "htf": htf,
                "diagnostic_prior_trusted": False,
            }
        )
        body["output_hash"] = content_hash({k: v for k, v in body.items() if k != "output_hash"})
        return body
