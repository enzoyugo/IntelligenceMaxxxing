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
    """Who performed an action against the Engine."""

    HUMAN = "HUMAN"
    APPLICATION = "APPLICATION"
    ENGINE = "ENGINE"
    LLM = "LLM"
    SYSTEM = "SYSTEM"


class HypothesisStatus(StrEnum):
    """Hypothesis lifecycle (Constitution, Article 13)."""

    PROPOSED = "PROPOSED"
    UNDER_OBSERVATION = "UNDER_OBSERVATION"
    UNDER_TEST = "UNDER_TEST"
    SUPPORTED = "SUPPORTED"
    WEAKENED = "WEAKENED"
    REJECTED_UNDER_CURRENT_CONDITIONS = "REJECTED_UNDER_CURRENT_CONDITIONS"
    INCONCLUSIVE = "INCONCLUSIVE"
    RETIRED = "RETIRED"
    REACTIVATED = "REACTIVATED"
