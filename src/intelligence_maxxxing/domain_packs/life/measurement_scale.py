"""Explicit wellbeing measurement scale contract (no magnitude inference).

Canonical score space for V1/V2 formulas: 0–100.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

MEASUREMENT_CONTRACT_VERSION = "wellbeing_measurements_v1"
NORMALIZATION_VERSION = "canonical_0_100_v1"

SCORE_FIELDS = ("happiness", "stress", "energy", "productivity")


class MeasurementScale(StrEnum):
    SCORE_0_100 = "0_100"
    LIKERT_1_10 = "1_10"


class ScaleResolutionSource(StrEnum):
    EXPLICIT_FIELD = "explicit_field"
    CONTRACT_VERSION = "contract_version"
    LEGACY_ADAPTER = "legacy_adapter"
    # Never used for productive snapshots:
    # MAGNITUDE_HEURISTIC


class MeasurementScaleError(Exception):
    """Typed contract failure for measurement scales."""

    code = "MEASUREMENT_SCALE_UNKNOWN"

    def __init__(self, message: str, *, code: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details or {}


class MeasurementScaleMissing(MeasurementScaleError):
    code = "MEASUREMENT_SCALE_MISSING"


class MeasurementScaleUnknown(MeasurementScaleError):
    code = "MEASUREMENT_SCALE_UNKNOWN"


class MeasurementOutOfRange(MeasurementScaleError):
    code = "MEASUREMENT_OUT_OF_RANGE"


class MeasurementContractUnsupported(MeasurementScaleError):
    code = "MEASUREMENT_CONTRACT_UNSUPPORTED"


class MeasurementScaleConflict(MeasurementScaleError):
    code = "MEASUREMENT_SCALE_CONFLICT"


@dataclass(frozen=True)
class ResolvedMeasurement:
    field: str
    raw_value: float
    declared_scale: MeasurementScale
    normalized_value: float
    scale_source: ScaleResolutionSource
    normalization_version: str = NORMALIZATION_VERSION


@dataclass
class ScaleExtractionReport:
    explicit_count: int = 0
    legacy_count: int = 0
    ambiguous_count: int = 0
    invalid_count: int = 0
    resolutions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total_score_fields(self) -> int:
        return self.explicit_count + self.legacy_count + self.ambiguous_count + self.invalid_count

    @property
    def explicit_scale_ratio(self) -> float:
        t = self.explicit_count + self.legacy_count
        return (self.explicit_count / t) if t else 0.0

    @property
    def legacy_scale_ratio(self) -> float:
        t = self.explicit_count + self.legacy_count
        return (self.legacy_count / t) if t else 0.0

    def as_features(self) -> dict[str, Any]:
        return {
            "measurement_contract_version": MEASUREMENT_CONTRACT_VERSION,
            "input_normalization_version": NORMALIZATION_VERSION,
            "explicit_scale_ratio": round(self.explicit_scale_ratio, 4),
            "legacy_scale_ratio": round(self.legacy_scale_ratio, 4),
            "ambiguous_scale_count": self.ambiguous_count,
            "invalid_measurement_count": self.invalid_count,
            "scale_resolution_summary": {
                "explicit": self.explicit_count,
                "legacy": self.legacy_count,
                "ambiguous": self.ambiguous_count,
                "invalid": self.invalid_count,
            },
        }


def parse_scale(raw: Any) -> MeasurementScale | None:
    if raw is None:
        return None
    text = str(raw).strip()
    aliases = {
        "0_100": MeasurementScale.SCORE_0_100,
        "score_0_100": MeasurementScale.SCORE_0_100,
        "SCORE_0_100": MeasurementScale.SCORE_0_100,
        "1_10": MeasurementScale.LIKERT_1_10,
        "likert_1_10": MeasurementScale.LIKERT_1_10,
        "LIKERT_1_10": MeasurementScale.LIKERT_1_10,
    }
    if text not in aliases:
        raise MeasurementScaleUnknown(
            f"unknown measurement scale: {raw!r}",
            details={"scale": text},
        )
    return aliases[text]


def validate_range(value: float, scale: MeasurementScale, *, field: str) -> None:
    if value != value or value in (float("inf"), float("-inf")):  # NaN/inf
        raise MeasurementOutOfRange(
            f"{field} is not a finite number",
            details={"field": field, "value": value, "scale": scale.value},
        )
    if scale is MeasurementScale.SCORE_0_100:
        if not (0.0 <= value <= 100.0):
            raise MeasurementOutOfRange(
                f"{field}={value} out of range for 0_100",
                details={"field": field, "value": value, "scale": scale.value},
            )
    elif scale is MeasurementScale.LIKERT_1_10:
        if not (1.0 <= value <= 10.0):
            raise MeasurementOutOfRange(
                f"{field}={value} out of range for 1_10",
                details={"field": field, "value": value, "scale": scale.value},
            )


def to_canonical_0_100(value: float, scale: MeasurementScale) -> float:
    """Convert once into 0–100. Likert: 1→0, 10→100."""
    validate_range(value, scale, field="value")
    if scale is MeasurementScale.SCORE_0_100:
        return float(value)
    # LIKERT_1_10
    return (float(value) - 1.0) / 9.0 * 100.0


def _legacy_scale_for(
    *,
    event_type: str | None,
    source_ids: list[str] | None,
    metadata: dict[str, Any] | None,
) -> MeasurementScale | None:
    """Known legacy contracts only — never magnitude."""
    meta = metadata or {}
    source_ids = source_ids or []
    # Explicit fixture / test tags
    if meta.get("legacy_scale") == MeasurementScale.LIKERT_1_10.value:
        return MeasurementScale.LIKERT_1_10
    if meta.get("legacy_scale") == MeasurementScale.SCORE_0_100.value:
        return MeasurementScale.SCORE_0_100
    # LifeOS Daily Flow (ValueSlider 1–10) via source URI
    if any(str(s).startswith("lifemaxxxing://daily-check-ins/") for s in source_ids):
        return MeasurementScale.LIKERT_1_10
    if event_type == "life.daily_check_in.completed.v1" and meta.get("source_system") == "lifeos":
        return MeasurementScale.LIKERT_1_10
    # Unit-test helper tag
    if meta.get("test_fixture_scale") == "1_10":
        return MeasurementScale.LIKERT_1_10
    return None


def resolve_field_scale(
    field: str,
    attrs: dict[str, Any],
    *,
    event_type: str | None = None,
    source_ids: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[MeasurementScale, ScaleResolutionSource]:
    """Precedence: explicit field → contract version → legacy adapter → error."""
    explicit_key = f"{field}_scale"
    if explicit_key in attrs and attrs[explicit_key] is not None:
        return parse_scale(attrs[explicit_key]), ScaleResolutionSource.EXPLICIT_FIELD

    contract = attrs.get("measurement_contract_version")
    if contract is not None:
        if str(contract) != MEASUREMENT_CONTRACT_VERSION:
            raise MeasurementContractUnsupported(
                f"unsupported measurement_contract_version: {contract!r}",
                details={"contract": contract},
            )
        # Contract known but per-field scale missing → still an error (must be explicit).
        raise MeasurementScaleMissing(
            f"{explicit_key} required when measurement_contract_version is set",
            details={"field": field, "contract": contract},
        )

    legacy = _legacy_scale_for(event_type=event_type, source_ids=source_ids, metadata=metadata)
    if legacy is not None:
        return legacy, ScaleResolutionSource.LEGACY_ADAPTER

    raise MeasurementScaleMissing(
        f"no scale for {field}: declare {explicit_key} or known legacy contract",
        details={"field": field},
    )


def resolve_measurement(
    field: str,
    attrs: dict[str, Any],
    *,
    event_type: str | None = None,
    source_ids: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ResolvedMeasurement:
    if field not in SCORE_FIELDS:
        raise MeasurementScaleUnknown(f"{field} is not a score measurement field")
    raw = attrs.get(field)
    if raw is None:
        raise MeasurementScaleMissing(f"{field} missing", details={"field": field})
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise MeasurementOutOfRange(
            f"{field} is not numeric",
            details={"field": field, "raw": raw},
        ) from exc

    scale, source = resolve_field_scale(
        field,
        attrs,
        event_type=event_type,
        source_ids=source_ids,
        metadata=metadata,
    )
    validate_range(value, scale, field=field)
    normalized = to_canonical_0_100(value, scale)
    return ResolvedMeasurement(
        field=field,
        raw_value=value,
        declared_scale=scale,
        normalized_value=normalized,
        scale_source=source,
    )


def resolve_score_fields(
    attrs: dict[str, Any],
    *,
    event_type: str | None = None,
    source_ids: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    report: ScaleExtractionReport | None = None,
) -> dict[str, float | None]:
    """Resolve SCORE_FIELDS to canonical 0–100; invalid/ambiguous → None."""
    report = report or ScaleExtractionReport()
    out: dict[str, float | None] = {f: None for f in SCORE_FIELDS}
    for field in SCORE_FIELDS:
        if attrs.get(field) is None:
            continue
        try:
            resolved = resolve_measurement(
                field,
                attrs,
                event_type=event_type,
                source_ids=source_ids,
                metadata=metadata,
            )
            out[field] = resolved.normalized_value
            if resolved.scale_source is ScaleResolutionSource.EXPLICIT_FIELD:
                report.explicit_count += 1
            else:
                report.legacy_count += 1
            report.resolutions.append(
                {
                    "field": field,
                    "raw": resolved.raw_value,
                    "scale": resolved.declared_scale.value,
                    "normalized": round(resolved.normalized_value, 4),
                    "source": resolved.scale_source.value,
                }
            )
        except MeasurementScaleMissing:
            report.ambiguous_count += 1
        except (MeasurementOutOfRange, MeasurementScaleUnknown, MeasurementContractUnsupported, MeasurementScaleConflict):
            report.invalid_count += 1
        except MeasurementScaleError:
            report.invalid_count += 1
    return out
