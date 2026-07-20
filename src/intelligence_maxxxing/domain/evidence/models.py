"""Evidence contracts.

Stage 0 `Evidence` remains the constitutional material-object stub.
Stage 3 `EvidenceSnapshot` is the frozen analysis artifact produced by a
governed evaluation (baseline exploratory or prospective validation).
"""

from pydantic import Field

from intelligence_maxxxing.domain.common.base import CanonicalObject, DomainModel, UtcDatetime
from intelligence_maxxxing.domain.common.epistemic import EvidencePhase
from intelligence_maxxxing.domain.common.knowledge import KnowledgeObject


class Evidence(KnowledgeObject):
    """A traceable piece of evidence supporting or weakening an assertion."""

    supports_object_ids: tuple[str, ...] = ()
    weakens_object_ids: tuple[str, ...] = ()
    methodology: str | None = None
    sample_description: str | None = None
    independence_notes: str | None = Field(
        default=None,
        description="Dependency on other sources; dependent evidence must not count twice",
    )


class AnalysisResult(DomainModel):
    """Serializable output of Bayesian Bootstrap Difference in Means v1."""

    method: str
    draws: int
    seed: str
    posterior_median_delta: float
    posterior_mean_delta: float
    credible_interval_90_low: float
    credible_interval_90_high: float
    credible_interval_95_low: float
    credible_interval_95_high: float
    p_delta_gt_0: float = Field(ge=0.0, le=1.0)
    p_delta_ge_mmd: float = Field(ge=0.0, le=1.0)
    mean_sufficient: float | None = None
    mean_below: float | None = None
    n_sufficient: int = 0
    n_below: int = 0


class ConfoundingDiagnostic(DomainModel):
    variable: str
    sufficient_n: int
    below_n: int
    sufficient_mean_or_proportion: float | None
    below_mean_or_proportion: float | None
    absolute_difference: float | None
    missingness_sufficient: float
    missingness_below: float
    potential_confounding: bool


class EvidenceSnapshot(CanonicalObject):
    """Frozen analysis of an eligible observation cohort for one experiment phase."""

    hypothesis_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    application_id: str = Field(min_length=1)
    phase: EvidencePhase
    source_observation_ids: tuple[str, ...]
    source_event_ids: tuple[str, ...]
    source_hash: str = Field(min_length=1)
    eligible_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    exclusion_reasons: dict[str, int] = Field(default_factory=dict)
    group_counts: dict[str, int] = Field(default_factory=dict)
    descriptive_statistics: dict[str, object] = Field(default_factory=dict)
    analysis_parameters: dict[str, object] = Field(default_factory=dict)
    analysis_result: AnalysisResult | None = None
    confounding_diagnostics: tuple[ConfoundingDiagnostic, ...] = ()
    limitations: tuple[str, ...] = ()
    generated_at: UtcDatetime
    audit_id: str = Field(min_length=1)
