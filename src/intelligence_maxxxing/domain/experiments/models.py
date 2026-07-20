"""Experiment protocol (Epistemic Standard §10; Stage 3 pre-registration).

Pre-registered before any prospective evaluation. Parameters cannot change
after registration without retiring the parent hypothesis.
"""

from pydantic import Field

from intelligence_maxxxing.domain.common.base import CanonicalObject, UtcDatetime


class ExperimentProtocol(CanonicalObject):
    """A pre-registered experiment design tied to one hypothesis."""

    protocol_version: str = Field(min_length=1)
    hypothesis_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    application_id: str = Field(min_length=1)
    analysis_method: str = Field(min_length=1)
    exposure_definition: str = Field(min_length=1)
    outcome_definition: str = Field(min_length=1)
    eligibility_rules: dict[str, object] = Field(default_factory=dict)
    baseline_cutoff: UtcDatetime
    prospective_start: UtcDatetime
    prospective_target: int = Field(ge=1)
    maximum_window_days: int = Field(ge=1)
    minimum_group_size: int = Field(ge=1)
    minimum_meaningful_difference: float
    sleep_threshold_hours: float
    stopping_rules: tuple[str, ...] = ()
    random_seed_policy: str = Field(min_length=1)
    pre_registered_at: UtcDatetime
    audit_id: str = Field(min_length=1)
    status: str = Field(default="REGISTERED", min_length=1)


# Stage 0 contract alias — ExperimentProtocol is the Stage 3 material object.
Experiment = ExperimentProtocol
