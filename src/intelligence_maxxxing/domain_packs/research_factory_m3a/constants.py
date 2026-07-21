"""M3A constants — frozen foundation identity."""

from __future__ import annotations

RESEARCH_FACTORY_ID = "IM_RESEARCH_FACTORY_M3A"
M3A_VERSION = "1.0.0"

HYPOTHESIS_SCHEMA = "im.research.hypothesis.v1"
EVIDENCE_SCHEMA = "im.research.evidence.v1"
EXPERIMENT_SCHEMA = "im.research.experiment.v1"
LEARNING_SCHEMA = "im.research.learning_memory.v1"

HYPOTHESIS_STATUSES = frozenset(
    {
        "DRAFT",
        "ACTIVE_OBSERVATION",
        "READY_FOR_EXPERIMENT",
        "EXPERIMENT_RUNNING",
        "SUPPORTED_PRELIMINARY",
        "CONTRADICTED_PRELIMINARY",
        "INCONCLUSIVE",
        "BLOCKED_DATA_QUALITY",
        "RETIRED",
        "SUPERSEDED",
    }
)

EVIDENCE_DIRECTIONS = frozenset({"SUPPORTING", "CONTRADICTING", "NEUTRAL", "DATA_QUALITY"})
EVIDENCE_TYPES = frozenset(
    {
        "PROSPECTIVE_OBSERVATION",
        "RETROSPECTIVE_DIAGNOSTIC",
        "DATA_QUALITY_FINDING",
        "CONTEXT_FINDING",
        "ANOMALY_FINDING",
        "CRITIC_REVIEW",
        "EXPERIMENT_RESULT",
        "POLICY_EVALUATION",
        "OPERATIONAL_HEALTH",
        "EXTERNAL_STATIC_EVIDENCE",
    }
)

EXPERIMENT_STATUSES = frozenset(
    {
        "DRAFT",
        "PRE_REGISTERED",
        "REVIEW_REQUIRED",
        "MANUALLY_APPROVED",
        "RUNNING",
        "PAUSED",
        "COMPLETED",
        "BLOCKED",
        "REJECTED",
        "CANCELLED",
    }
)

# Agents may only create DRAFT hypotheses.
AGENT_ALLOWED_HYPOTHESIS_STATUS = "DRAFT"
MAX_AGENT_PROPOSALS_PER_CYCLE = 5
