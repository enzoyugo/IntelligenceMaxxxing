"""AnomalyAgentV1 — append-only findings; baselines use prior-only evidence."""

from __future__ import annotations

from typing import Any

from intelligence_maxxxing.domain_packs.trading.agent_bundle_v1 import (
    AGENT_BUNDLE_VERSION,
    ANOMALY_SCHEMA_VERSION,
    THRESHOLDS,
)
from intelligence_maxxxing.domain_packs.trading.agents._common import (
    content_hash,
    feature_value,
    has_forbidden_outcome_fields,
    new_id,
    pit_feature_violations,
    utc_now,
)

AGENT_ID = "AnomalyAgentV1"
AGENT_VERSION = "1.0.0"


def _finding(
    *,
    observation: dict[str, Any],
    anomaly_type: str,
    severity: str,
    confidence: float,
    reason_codes: list[str],
    hard_gate_implication: str | None,
    limitations: list[str],
    evidence_window_end: str,
    point_in_time_valid: bool,
) -> dict[str, Any]:
    setup = observation.get("economic_setup") or {}
    body: dict[str, Any] = {
        "schema_version": ANOMALY_SCHEMA_VERSION,
        "finding_id": new_id("ANOM"),
        "observation_id": observation.get("observation_id"),
        "economic_setup_id": setup.get("economic_setup_id"),
        "agent_id": AGENT_ID,
        "agent_version": AGENT_VERSION,
        "agent_bundle_version": AGENT_BUNDLE_VERSION,
        "anomaly_type": anomaly_type,
        "severity": severity,
        "confidence": confidence,
        "detected_at": utc_now(),
        "evidence_window_end": evidence_window_end,
        "evidence_refs": [
            f"observation:{observation.get('observation_id')}",
            f"setup:{setup.get('economic_setup_id')}",
        ],
        "reason_codes": reason_codes,
        "point_in_time_valid": point_in_time_valid,
        "hard_gate_implication": hard_gate_implication,
        "limitations": limitations,
        "outcome_access_count": 0,
        "research_only": True,
    }
    body["input_hash"] = content_hash(
        {
            "observation_id": observation.get("observation_id"),
            "anomaly_type": anomaly_type,
            "decision_cutoff_utc": observation.get("decision_cutoff_utc"),
        }
    )
    body["output_hash"] = content_hash({k: v for k, v in body.items() if k != "output_hash"})
    return body


class AnomalyAgentV1:
    agent_id = AGENT_ID
    agent_version = AGENT_VERSION

    def __init__(self) -> None:
        # Prior observation ids for duplicate detection within a run (append-only memory).
        self._seen_observation_ids: set[str] = set()
        self._seen_setup_ids: set[str] = set()

    def detect(
        self,
        observation: dict[str, Any],
        *,
        prior_findings: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        _ = prior_findings  # reserved for fold baselines; must not use future outcomes
        findings: list[dict[str, Any]] = []
        cutoff = str(observation.get("decision_cutoff_utc") or "")
        setup = observation.get("economic_setup") or {}
        obs_id = str(observation.get("observation_id") or "")
        setup_id = str(setup.get("economic_setup_id") or "")
        pit = pit_feature_violations(observation)
        leaks = has_forbidden_outcome_fields(observation)
        limitations = ["NO_OUTCOME_BASELINE", "DETERMINISTIC_V1", "OLLAMA_NOT_REQUIRED"]

        origin = str(observation.get("origin") or observation.get("dataset_origin") or "").upper()
        experiment_mode = str(observation.get("experiment_mode") or "").upper()
        if origin in {"TEST_OOS", "FORWARD"} and experiment_mode == "RETROSPECTIVE_DIAGNOSTIC":
            findings.append(
                _finding(
                    observation=observation,
                    anomaly_type="REPLAY_ORIGIN_VIOLATION",
                    severity="CRITICAL",
                    confidence=1.0,
                    reason_codes=["ORIGIN_VIOLATION", f"ORIGIN_{origin}"],
                    hard_gate_implication="REJECT_ROW",
                    limitations=limitations,
                    evidence_window_end=cutoff or utc_now(),
                    point_in_time_valid=True,
                )
            )

        if obs_id and obs_id in self._seen_observation_ids:
            findings.append(
                _finding(
                    observation=observation,
                    anomaly_type="DUPLICATE_OBSERVATION",
                    severity="HIGH",
                    confidence=0.95,
                    reason_codes=["DUPLICATE_OBSERVATION"],
                    hard_gate_implication="DEFER",
                    limitations=limitations,
                    evidence_window_end=cutoff or utc_now(),
                    point_in_time_valid=True,
                )
            )
        if obs_id:
            self._seen_observation_ids.add(obs_id)

        if setup_id and setup_id in self._seen_setup_ids and experiment_mode == "RETROSPECTIVE_DIAGNOSTIC":
            findings.append(
                _finding(
                    observation=observation,
                    anomaly_type="ECONOMIC_IDENTITY_CONFLICT",
                    severity="MEDIUM",
                    confidence=0.7,
                    reason_codes=["ECONOMIC_IDENTITY_CONFLICT"],
                    hard_gate_implication=None,
                    limitations=limitations,
                    evidence_window_end=cutoff or utc_now(),
                    point_in_time_valid=True,
                )
            )
        if setup_id:
            self._seen_setup_ids.add(setup_id)

        if pit:
            findings.append(
                _finding(
                    observation=observation,
                    anomaly_type="FEATURE_DRIFT",
                    severity="CRITICAL",
                    confidence=1.0,
                    reason_codes=["FUTURE_FEATURE", *pit[:4]],
                    hard_gate_implication="DEFER_DATA_QUALITY",
                    limitations=limitations + ["POINT_IN_TIME_VIOLATION"],
                    evidence_window_end=cutoff or utc_now(),
                    point_in_time_valid=False,
                )
            )

        if leaks:
            findings.append(
                _finding(
                    observation=observation,
                    anomaly_type="SCHEMA_DRIFT",
                    severity="CRITICAL",
                    confidence=1.0,
                    reason_codes=["OUTCOME_OR_FUTURE_FIELD_PRESENT", *leaks[:4]],
                    hard_gate_implication="DEFER_DATA_QUALITY",
                    limitations=limitations,
                    evidence_window_end=cutoff or utc_now(),
                    point_in_time_valid=False,
                )
            )

        dq = observation.get("data_quality") or {}
        quote_q = str(dq.get("quote_quality") or "").upper()
        if quote_q in {"QUOTE_FUTURE_REJECTED"}:
            findings.append(
                _finding(
                    observation=observation,
                    anomaly_type="QUOTE_FUTURE_OR_STALE",
                    severity="CRITICAL",
                    confidence=1.0,
                    reason_codes=["QUOTE_FUTURE"],
                    hard_gate_implication="DEFER_DATA_QUALITY",
                    limitations=limitations,
                    evidence_window_end=cutoff or utc_now(),
                    point_in_time_valid=True,
                )
            )
        elif quote_q in {"QUOTE_STALE"}:
            findings.append(
                _finding(
                    observation=observation,
                    anomaly_type="QUOTE_FUTURE_OR_STALE",
                    severity="MEDIUM",
                    confidence=0.8,
                    reason_codes=["QUOTE_STALE"],
                    hard_gate_implication=None,
                    limitations=limitations,
                    evidence_window_end=cutoff or utc_now(),
                    point_in_time_valid=True,
                )
            )
        elif quote_q in {"", "QUOTE_UNAVAILABLE", "QUOTE_MISSING", "NONE"}:
            findings.append(
                _finding(
                    observation=observation,
                    anomaly_type="QUOTE_FUTURE_OR_STALE",
                    severity="HIGH",
                    confidence=0.9,
                    reason_codes=["QUOTE_UNAVAILABLE"],
                    hard_gate_implication="DEFER_DATA_QUALITY",
                    limitations=limitations,
                    evidence_window_end=cutoff or utc_now(),
                    point_in_time_valid=True,
                )
            )

        cost_q = str(dq.get("cost_quality") or "").upper()
        if cost_q in {"", "COST_UNAVAILABLE", "NONE", "COST_INCOMPLETE"}:
            findings.append(
                _finding(
                    observation=observation,
                    anomaly_type="COST_COVERAGE_ANOMALY",
                    severity="INFO",
                    confidence=0.7,
                    reason_codes=["COST_COVERAGE_INCOMPLETE"],
                    hard_gate_implication=None,
                    limitations=limitations + ["MISSING_COST_NOT_ZERO"],
                    evidence_window_end=cutoff or utc_now(),
                    point_in_time_valid=True,
                )
            )

        spread = feature_value(observation, "spread_price")
        try:
            s = float(spread) if spread is not None else None
        except (TypeError, ValueError):
            s = None
        if s is not None and s >= THRESHOLDS["spread_extreme"]:
            findings.append(
                _finding(
                    observation=observation,
                    anomaly_type="SPREAD_SPIKE",
                    severity="HIGH",
                    confidence=0.85,
                    reason_codes=["SPREAD_EXTREME"],
                    hard_gate_implication=None,
                    limitations=limitations,
                    evidence_window_end=cutoff or utc_now(),
                    point_in_time_valid=True,
                )
            )
        elif s is not None and s >= THRESHOLDS["spread_high"]:
            findings.append(
                _finding(
                    observation=observation,
                    anomaly_type="SPREAD_SPIKE",
                    severity="MEDIUM",
                    confidence=0.75,
                    reason_codes=["SPREAD_HIGH"],
                    hard_gate_implication=None,
                    limitations=limitations,
                    evidence_window_end=cutoff or utc_now(),
                    point_in_time_valid=True,
                )
            )

        entry = setup.get("entry")
        stop = setup.get("stop") if setup.get("stop") is not None else setup.get("stop_loss")
        target = setup.get("target") if setup.get("target") is not None else setup.get("take_profit")
        direction = str(setup.get("direction") or "").upper()
        try:
            if entry is not None and stop is not None and target is not None:
                e, sl, tp = float(entry), float(stop), float(target)
                invalid = False
                if direction in {"LONG", "BUY"} and not (sl < e < tp):
                    invalid = True
                if direction in {"SHORT", "SELL"} and not (tp < e < sl):
                    invalid = True
                if invalid:
                    findings.append(
                        _finding(
                            observation=observation,
                            anomaly_type="INVALID_STOP_TARGET_RELATIONSHIP",
                            severity="HIGH",
                            confidence=0.9,
                            reason_codes=["GEOMETRY_OUTLIER"],
                            hard_gate_implication=None,
                            limitations=limitations,
                            evidence_window_end=cutoff or utc_now(),
                            point_in_time_valid=True,
                        )
                    )
        except (TypeError, ValueError):
            findings.append(
                _finding(
                    observation=observation,
                    anomaly_type="GEOMETRY_OUTLIER",
                    severity="MEDIUM",
                    confidence=0.6,
                    reason_codes=["GEOMETRY_PARSE_FAILED"],
                    hard_gate_implication=None,
                    limitations=limitations,
                    evidence_window_end=cutoff or utc_now(),
                    point_in_time_valid=True,
                )
            )

        raw = observation.get("raw_strategy") or {}
        native = observation.get("tmx_native") or {}
        if raw.get("decision") == "TAKE" and native.get("decision") == "SKIP":
            findings.append(
                _finding(
                    observation=observation,
                    anomaly_type="LANE_CONFLICT",
                    severity="LOW",
                    confidence=0.65,
                    reason_codes=["LANE_CONFLICT_RAW_TAKE_NATIVE_SKIP"],
                    hard_gate_implication=None,
                    limitations=limitations,
                    evidence_window_end=cutoff or utc_now(),
                    point_in_time_valid=True,
                )
            )

        if not observation.get("provenance") and not observation.get("source_commit"):
            findings.append(
                _finding(
                    observation=observation,
                    anomaly_type="MISSING_PROVENANCE",
                    severity="LOW",
                    confidence=0.55,
                    reason_codes=["MISSING_PROVENANCE"],
                    hard_gate_implication=None,
                    limitations=limitations,
                    evidence_window_end=cutoff or utc_now(),
                    point_in_time_valid=True,
                )
            )

        # Stable empty finding marker when clean — callers may filter INFO CLEAN.
        if not findings:
            findings.append(
                _finding(
                    observation=observation,
                    anomaly_type="NO_ANOMALY",
                    severity="INFO",
                    confidence=0.5,
                    reason_codes=["NO_ANOMALY_DETECTED"],
                    hard_gate_implication=None,
                    limitations=limitations,
                    evidence_window_end=cutoff or utc_now(),
                    point_in_time_valid=len(pit) == 0,
                )
            )
        return findings
