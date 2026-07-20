"""Epistemic classification enums mandated by EPISTEMIC_STANDARD.md v1.0."""

from enum import StrEnum


class KnowledgeClass(StrEnum):
    """Mandatory primary class for every knowledge object (Epistemic Standard §2)."""

    OBSERVED_FACT = "OBSERVED_FACT"
    DERIVED_FACT = "DERIVED_FACT"
    INFERENCE = "INFERENCE"
    HYPOTHESIS = "HYPOTHESIS"
    EXPERIMENTAL_RESULT = "EXPERIMENTAL_RESULT"
    SUPPORTED_CONCLUSION = "SUPPORTED_CONCLUSION"
    OPERATIONAL_BELIEF = "OPERATIONAL_BELIEF"
    HUMAN_VALUE = "HUMAN_VALUE"
    UNKNOWN = "UNKNOWN"


class UnknownReason(StrEnum):
    """Mandatory reason whenever knowledge_class is UNKNOWN (Epistemic Standard §3)."""

    MISSING_DATA = "MISSING_DATA"
    CONTRADICTORY_DATA = "CONTRADICTORY_DATA"
    NOT_MEASURABLE_DIRECTLY = "NOT_MEASURABLE_DIRECTLY"
    INHERENT_RANDOMNESS = "INHERENT_RANDOMNESS"
    METHOD_LIMITATION = "METHOD_LIMITATION"
    OUT_OF_DISTRIBUTION = "OUT_OF_DISTRIBUTION"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    INSUFFICIENT_POWER = "INSUFFICIENT_POWER"


class CausalityLevel(StrEnum):
    """Causality ladder (Epistemic Standard §9)."""

    CORRELATION = "CORRELATION"
    PLAUSIBLE_CAUSAL_LINK = "PLAUSIBLE_CAUSAL_LINK"
    CAUSAL_EVIDENCE = "CAUSAL_EVIDENCE"
    REPLICATED_CAUSAL_EVIDENCE = "REPLICATED_CAUSAL_EVIDENCE"


class ConfidenceLevel(StrEnum):
    """Categorical confidence labels (Epistemic Standard §4.1)."""

    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class FreshnessState(StrEnum):
    """Freshness marker; decay policies belong to Domain Packs (Epistemic Standard §7)."""

    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class SourceType(StrEnum):
    """Default evidence hierarchy (Epistemic Standard §5). A prior, not a verdict."""

    DIRECT_PRIMARY_MEASUREMENT = "DIRECT_PRIMARY_MEASUREMENT"
    AUDITED_PRIMARY_DATASET = "AUDITED_PRIMARY_DATASET"
    REPRODUCIBLE_EXPERIMENT = "REPRODUCIBLE_EXPERIMENT"
    INDEPENDENT_OFFICIAL_SOURCE = "INDEPENDENT_OFFICIAL_SOURCE"
    RELIABLE_SECONDARY_SOURCE = "RELIABLE_SECONDARY_SOURCE"
    HUMAN_OBSERVATION = "HUMAN_OBSERVATION"
    MODEL_INFERENCE = "MODEL_INFERENCE"
    UNVERIFIED = "UNVERIFIED"


class ActorType(StrEnum):
    """Who performed an action against the Engine.

    HUMAN/APPLICATION/SERVICE/AI_AGENT/SYSTEM are the canonical Stage 1 types.
    ENGINE and LLM remain for backward compatibility with Stage 0 events
    (LLM is a specialization of AI_AGENT; ENGINE of SERVICE).
    """

    HUMAN = "HUMAN"
    APPLICATION = "APPLICATION"
    SERVICE = "SERVICE"
    AI_AGENT = "AI_AGENT"
    SYSTEM = "SYSTEM"
    ENGINE = "ENGINE"
    LLM = "LLM"


class HypothesisStatus(StrEnum):
    """Hypothesis lifecycle (Constitution Art. 13; Stage 3 first epistemic loop).

    Stage 0 names (UNDER_OBSERVATION, UNDER_TEST, …) remain for contract
    compatibility. Stage 3 operational statuses are the primary path.
    """

    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    OBSERVING = "OBSERVING"
    EVALUATED = "EVALUATED"
    WEAKENED = "WEAKENED"
    SUPPORTED = "SUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    RETIRED = "RETIRED"
    # Legacy Stage 0 aliases (still valid enum members for stored contracts).
    UNDER_OBSERVATION = "UNDER_OBSERVATION"
    UNDER_TEST = "UNDER_TEST"
    REJECTED_UNDER_CURRENT_CONDITIONS = "REJECTED_UNDER_CURRENT_CONDITIONS"
    REACTIVATED = "REACTIVATED"


class EvidencePhase(StrEnum):
    """Which cohort an EvidenceSnapshot describes."""

    BASELINE_EXPLORATORY = "BASELINE_EXPLORATORY"
    PROSPECTIVE_VALIDATION = "PROSPECTIVE_VALIDATION"


class BeliefState(StrEnum):
    """Operational belief classification for the sleep/productivity protocol."""

    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    EXPLORATORY_POSITIVE = "EXPLORATORY_POSITIVE"
    EXPLORATORY_NEGATIVE = "EXPLORATORY_NEGATIVE"
    EXPLORATORY_INCONCLUSIVE = "EXPLORATORY_INCONCLUSIVE"
    PROSPECTIVE_COLLECTING = "PROSPECTIVE_COLLECTING"
    PROSPECTIVE_SUPPORTED = "PROSPECTIVE_SUPPORTED"
    PROSPECTIVE_WEAKENED = "PROSPECTIVE_WEAKENED"
    PROSPECTIVE_INCONCLUSIVE = "PROSPECTIVE_INCONCLUSIVE"
    EXPIRED_INCONCLUSIVE = "EXPIRED_INCONCLUSIVE"


class EvaluationKind(StrEnum):
    INTERIM_EVALUATION = "INTERIM_EVALUATION"
    TERMINAL_EVALUATION = "TERMINAL_EVALUATION"


class TerminalReason(StrEnum):
    TARGET_REACHED = "TARGET_REACHED"
    MAXIMUM_WINDOW_EXPIRED = "MAXIMUM_WINDOW_EXPIRED"
    HUMAN_RETIRED = "HUMAN_RETIRED"
    DATA_QUALITY_TERMINATION = "DATA_QUALITY_TERMINATION"
    NOT_TERMINAL = "NOT_TERMINAL"


class CalibrationState(StrEnum):
    """Until enough historical experiments exist, beliefs stay uncalibrated."""

    UNCALIBRATED = "UNCALIBRATED"
    PARTIALLY_CALIBRATED = "PARTIALLY_CALIBRATED"
    CALIBRATED = "CALIBRATED"


class AgreementWithPrior(StrEnum):
    STRENGTHENED = "STRENGTHENED"
    WEAKENED = "WEAKENED"
    CONTRADICTED = "CONTRADICTED"
    UNCHANGED = "UNCHANGED"
    NOT_COMPARABLE = "NOT_COMPARABLE"


class LearningChangeType(StrEnum):
    PRIOR_STRENGTHENED = "PRIOR_STRENGTHENED"
    PRIOR_WEAKENED = "PRIOR_WEAKENED"
    PRIOR_CONTRADICTED = "PRIOR_CONTRADICTED"
    FIRST_PROSPECTIVE = "FIRST_PROSPECTIVE"
    EXPIRED = "EXPIRED"
    RETIRED = "RETIRED"
