"""IM_M2_AGENT_BUNDLE_MANIFEST_V1 — pre-registered before retrospective results.

Frozen at cutover. Bug fixes require 1.0.1 + fresh run; no post-hoc threshold tuning.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

AGENT_BUNDLE_ID = "IM_M2_AGENT_BUNDLE"
AGENT_BUNDLE_VERSION = "1.0.0"
CONTEXT_SCHEMA_VERSION = "im.trading.context_assessment.v1"
ANOMALY_SCHEMA_VERSION = "im.trading.anomaly_finding.v1"
CRITIC_SCHEMA_VERSION = "im.trading.critic_review.v1"
SHADOW_ADJUDICATION_SCHEMA_VERSION = "im.trading.shadow_adjudication.v1"
FEATURE_REGISTRY_ID = "IM_TRADING_POINT_IN_TIME_FEATURE_REGISTRY_V1"

# Canonical split (must match TMX bias_free_backtest_protocol_v1.SPLITS_2Y).
SPLIT_BOUNDARIES = {
    "train": {"start": "2024-07-01", "end": "2025-06-30"},
    "validation": {"start": "2025-07-01", "end": "2025-12-31"},
    "oos_test_frozen": {"start": "2026-01-01", "end": "2026-06-30"},
    "forward_paper": {"start": "2026-07-01", "end": None},
}

FEATURE_ALLOWLIST = (
    "spread_price",
    "spread_bucket",
    "session_label",
    "volatility_bucket",
    "trend_label",
    "liquidity_label",
    "quote_age_ms",
    "cost_quality_token",
    "fidelity_class",
    "direction",
    "symbol",
    "timeframe",
)

FEATURE_DENYLIST = (
    "outcome",
    "exit_reason",
    "exit_time",
    "realized_R",
    "gross_R",
    "trusted_net_R",
    "mfe",
    "mae",
    "resolved_at",
    "pnl",
    "post_cutover_performance",
    "forward_results",
)

REASON_CODES = (
    "CONTEXT_UNKNOWN",
    "SPREAD_HIGH",
    "SPREAD_EXTREME",
    "VOLATILITY_EXTREME",
    "QUOTE_STALE",
    "QUOTE_FUTURE",
    "DUPLICATE_OBSERVATION",
    "ORIGIN_VIOLATION",
    "FIDELITY_OBJECTION",
    "DATA_QUALITY_OBJECTION",
    "EVIDENCE_INSUFFICIENT",
    "CRITIC_CHALLENGE",
    "HARD_DQ_GATE",
    "ANOMALY_CRITICAL_DEFER",
    "NON_AUTHORITATIVE_SHADOW",
)

THRESHOLDS = {
    "spread_high": 0.00025,
    "spread_extreme": 0.00050,
    "quote_stale_ms": 5000,
    "context_confidence_unknown_below": 0.25,
    "critic_challenge_score": 0.55,
}

LOOKBACK_WINDOWS = {
    "spread_percentile_prior_days": 30,
    "anomaly_baseline_prior_days": 60,
}

STALENESS_BUDGETS = {
    "feature_max_age_ms": 60_000,
    "agent_timeout_ms": 2_000,
}

ABSTENTION_RULES = (
    "never_upgrade_unknown_to_take_from_context_alone",
    "hard_dq_dominates",
    "critical_anomaly_defers",
    "insufficient_evidence_unknown",
)

RESOURCE_BUDGETS = {
    "max_workers": 1,
    "ollama_required": False,
    "cpu_soft_pct": 70,
}

SUCCESS_CRITERIA = (
    "deterministic_agent_outputs",
    "point_in_time_valid",
    "zero_outcome_access",
    "test_oos_rows_read_eq_0",
    "forward_replay_rows_read_eq_0",
    "policy_1_0_0_unchanged",
    "shadow_non_authoritative",
)

FAILURE_CRITERIA = (
    "outcome_leakage",
    "future_feature",
    "oos_or_forward_replay_read",
    "policy_mutation",
    "shadow_replaces_im_advisory",
    "post_hoc_threshold_tuning",
)

REPLAY_MODE = "POINT_IN_TIME_RETROSPECTIVE_DECISION_REPLAY"
EXPERIMENT_ID_RETROSPECTIVE = "TMX_IM_RETROSPECTIVE_AGENT_REPLAY_V1"
EXPERIMENT_MODE = "RETROSPECTIVE_DIAGNOSTIC"

_MANIFEST_CANONICAL: dict[str, Any] = {
    "agent_bundle_id": AGENT_BUNDLE_ID,
    "agent_bundle_version": AGENT_BUNDLE_VERSION,
    "context_schema_version": CONTEXT_SCHEMA_VERSION,
    "anomaly_schema_version": ANOMALY_SCHEMA_VERSION,
    "critic_schema_version": CRITIC_SCHEMA_VERSION,
    "shadow_adjudication_schema_version": SHADOW_ADJUDICATION_SCHEMA_VERSION,
    "feature_registry_id": FEATURE_REGISTRY_ID,
    "feature_allowlist": list(FEATURE_ALLOWLIST),
    "feature_denylist": list(FEATURE_DENYLIST),
    "reason_codes": list(REASON_CODES),
    "thresholds": THRESHOLDS,
    "lookback_windows": LOOKBACK_WINDOWS,
    "staleness_budgets": STALENESS_BUDGETS,
    "abstention_rules": list(ABSTENTION_RULES),
    "resource_budgets": RESOURCE_BUDGETS,
    "success_criteria": list(SUCCESS_CRITERIA),
    "failure_criteria": list(FAILURE_CRITERIA),
    "split_boundaries": SPLIT_BOUNDARIES,
    "fidelity_rules": {
        "certified_primary": True,
        "partial_separated": True,
        "proxy_diagnostic_only": True,
        "deprecated_excluded_default": True,
        "no_unsafe_pooling": True,
    },
    "cost_rules": {
        "missing_cost_not_zero": True,
        "gross_not_trusted_net": True,
    },
    "replay_mode": REPLAY_MODE,
    "experiment_id_retrospective": EXPERIMENT_ID_RETROSPECTIVE,
    "experiment_mode": EXPERIMENT_MODE,
    "live_policy_influence": False,
    "promotion_eligible": False,
    "ollama_required": False,
    "pre_registered_before_results": True,
    "no_post_hoc_tuning": True,
}

BUNDLE_MANIFEST_HASH = hashlib.sha256(
    json.dumps(_MANIFEST_CANONICAL, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()


def active_bundle_manifest() -> dict[str, Any]:
    return {
        **_MANIFEST_CANONICAL,
        "manifest_hash": BUNDLE_MANIFEST_HASH,
        "research_only": True,
        "non_authoritative": True,
        "policy_frozen_reference": "IM_TRADING_DECISION_POLICY@1.0.0",
    }
