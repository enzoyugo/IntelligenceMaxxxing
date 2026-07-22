"""M3B Evidence / Safety / Report foundation constants — frozen identity."""

from __future__ import annotations

M3B_ID = "IM_RESEARCH_FACTORY_M3B"
M3B_VERSION = "1.0.0"

EVIDENCE_BUNDLE_SCHEMA = "im.research.evidence_bundle.v1"
SAFETY_AUDIT_SCHEMA = "im.research.safety_audit.v1"
STRUCTURED_REPORT_SCHEMA = "im.research.structured_report.v1"

EVIDENCE_ITEM_DIRECTIONS = frozenset(
    {"SUPPORTING", "CONTRADICTING", "NEUTRAL", "DATA_QUALITY", "PENDING_OUTCOME"}
)

TRUST_STATUSES = frozenset(
    {
        "TRUSTED",
        "PARTIAL",
        "CONFLICTED",
        "MISSING_EVIDENCE",
        "PENDING_OUTCOME",
        "DATA_QUALITY_BLOCKED",
        "FIXTURE_ONLY",
        "UNTRUSTED",
    }
)

OVERALL_SAFETY_STATUSES = frozenset(
    {
        "SAFETY_PASS",
        "SAFETY_PASS_WITH_WARNINGS",
        "SAFETY_PARTIAL",
        "SAFETY_BLOCKED",
    }
)

SAFETY_CHECK_STATUSES = frozenset({"PASS", "FAIL", "WARN", "UNKNOWN"})

REPORT_TYPES = frozenset(
    {
        "EVIDENCE_BUNDLE_SUMMARY",
        "SAFETY_AUDIT_SUMMARY",
        "ECONOMIC_INCREMENTAL_VALUE",
        "DAILY_RESEARCH_STATUS",
        "EXPERIMENT_READINESS",
        "REGISTRY_QUALITY",
    }
)

ECONOMIC_VERDICTS = frozenset(
    {
        "INSUFFICIENT_SAMPLE",
        "DATA_QUALITY_BLOCKED",
        "NO_INCREMENTAL_VALUE",
        "PRELIMINARY_INCREMENTAL_VALUE",
        "ROBUST_INCREMENTAL_VALUE_NOT_YET_PROVEN",
    }
)

FORBIDDEN_ECONOMIC_VERDICTS = frozenset(
    {
        "EDGE_CONFIRMED",
        "PROFITABLE_SYSTEM",
        "LIVE_READY",
    }
)

TEMPORAL_LABELS = frozenset({"PROSPECTIVE", "RETROSPECTIVE", "UNSPECIFIED"})
ORIGIN_LABELS = frozenset({"REAL", "FIXTURE", "CANARY", "MIXED", "UNKNOWN"})

CRITICAL_SAFETY_FAILURE_CODES = frozenset(
    {
        "BROKER_CALLS_DETECTED",
        "EXECUTION_ENABLED",
        "POLICY_MUTATION_DETECTED",
        "OOS_ROWS_READ",
        "FUTURE_FEATURES_DETECTED",
        "OUTCOME_LEAKAGE",
        "AUTO_RUN_ENABLED",
        "AUTO_PROMOTION_ENABLED",
        "TMX_STORAGE_ACCESS",
        "OLLAMA_INVOKED",
    }
)
