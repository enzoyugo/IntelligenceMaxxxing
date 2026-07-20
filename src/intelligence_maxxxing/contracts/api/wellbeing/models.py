"""Public wellbeing API schemas (ANALYZE / EXPLAIN). V1 + V2 SHADOW fields."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScoreBlockView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float | None = None
    baseline: float | None = None
    acute: float | None = None
    chronic: float | None = None
    anticipatory: float | None = None
    trend: str | None = None
    confidence: float | None = None
    plausible_range: list[float] | None = None
    sub_scores: dict[str, Any] = Field(default_factory=dict)


class WellbeingSnapshotView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score_snapshot_id: str
    formula_id: str
    formula_version: str
    formula_status: str | None = None
    happiness: float | None = None
    stress: float | None = None
    confidence: float | None = None
    early_warning: str
    data_sufficiency: str
    sample_size: int
    missing_days: int
    period_start: str
    period_end: str
    features: dict[str, Any] = Field(default_factory=dict)
    contributors: list[dict[str, Any]] = Field(default_factory=list)
    suggested_actions: list[dict[str, Any]] = Field(default_factory=list)
    explanation: dict[str, Any] = Field(default_factory=dict)
    baselines: dict[str, Any] = Field(default_factory=dict)
    computed_at: str
    as_of_global_position: int | None = None
    # V2 structured blocks (optional; absent for pure V1 snapshots)
    happiness_block: ScoreBlockView | None = None
    stress_block: ScoreBlockView | None = None
    overall_confidence: float | None = None
    change_state: str | None = None
    protective_factors: list[dict[str, Any]] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    data_quality: dict[str, Any] = Field(default_factory=dict)
    input_fingerprint: str | None = None
    as_of: str | None = None
    observation_cutoff: str | None = None


class WellbeingCurrentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: WellbeingSnapshotView


class WellbeingHistoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[WellbeingSnapshotView]
    next_cursor: str | None = None


class WellbeingFormulaData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    formula_id: str
    version: str
    description: str
    active: bool
    status: str | None = None
    happiness_neq_100_minus_stress: bool = True
    autonomy: list[str] = Field(default_factory=lambda: ["OBSERVE", "ANALYZE", "EXPLAIN"])
    forbidden_autonomy: list[str] = Field(
        default_factory=lambda: ["RECOMMEND", "EXECUTE", "OPTIMIZE_BEHAVIOR"]
    )
    weights: dict[str, Any] = Field(default_factory=dict)


class WellbeingFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score_snapshot_id: str | None = None
    rating: str = Field(min_length=1, max_length=32)
    note: str | None = Field(default=None, max_length=1000)


class WellbeingFeedbackResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback_id: str
    accepted: bool = True


class WellbeingShadowCompareData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    v1: WellbeingSnapshotView
    v2: WellbeingSnapshotView
    divergences: dict[str, Any] = Field(default_factory=dict)
