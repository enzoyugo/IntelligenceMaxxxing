"""Mandatory measurement scale contract matrix (no magnitude inference)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from intelligence_maxxxing.domain_packs.life.measurement_scale import (
    MEASUREMENT_CONTRACT_VERSION,
    NORMALIZATION_VERSION,
    MeasurementOutOfRange,
    MeasurementScale,
    MeasurementScaleMissing,
    MeasurementScaleUnknown,
    ScaleExtractionReport,
    resolve_measurement,
    resolve_score_fields,
    to_canonical_0_100,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v1 import extract_checkin_days


def test_0_100_boundary_values_preserved() -> None:
    for raw in (0, 1, 5, 10, 11, 50, 99, 100):
        n = to_canonical_0_100(float(raw), MeasurementScale.SCORE_0_100)
        assert n == float(raw)


def test_1_10_boundary_conversions() -> None:
    assert to_canonical_0_100(1.0, MeasurementScale.LIKERT_1_10) == 0.0
    assert abs(to_canonical_0_100(5.0, MeasurementScale.LIKERT_1_10) - (4.0 / 9.0 * 100.0)) < 1e-9
    assert to_canonical_0_100(10.0, MeasurementScale.LIKERT_1_10) == 100.0
    assert abs(to_canonical_0_100(2.0, MeasurementScale.LIKERT_1_10) - (1.0 / 9.0 * 100.0)) < 1e-9
    assert abs(to_canonical_0_100(9.0, MeasurementScale.LIKERT_1_10) - (8.0 / 9.0 * 100.0)) < 1e-9


@pytest.mark.parametrize("bad", [0.0, 11.0, -1.0, 101.0])
def test_1_10_rejects_out_of_range(bad: float) -> None:
    with pytest.raises(MeasurementOutOfRange):
        to_canonical_0_100(bad, MeasurementScale.LIKERT_1_10)


@pytest.mark.parametrize("bad", [-0.1, 100.1, float("nan"), float("inf")])
def test_0_100_rejects_out_of_range(bad: float) -> None:
    with pytest.raises(MeasurementOutOfRange):
        to_canonical_0_100(bad, MeasurementScale.SCORE_0_100)


def test_explicit_mixed_scales() -> None:
    attrs = {
        "happiness": 5,
        "happiness_scale": "0_100",
        "stress": 5,
        "stress_scale": "1_10",
        "energy": 50,
        "energy_scale": "0_100",
        "productivity": 10,
        "productivity_scale": "1_10",
        "measurement_contract_version": MEASUREMENT_CONTRACT_VERSION,
    }
    report = ScaleExtractionReport()
    out = resolve_score_fields(attrs, report=report)
    assert out["happiness"] == 5.0
    assert abs(out["stress"] - (4.0 / 9.0 * 100.0)) < 1e-9
    assert out["energy"] == 50.0
    assert out["productivity"] == 100.0
    assert report.explicit_count == 4
    assert report.ambiguous_count == 0


def test_missing_scale_is_ambiguous() -> None:
    report = ScaleExtractionReport()
    out = resolve_score_fields({"happiness": 5}, report=report)
    assert out["happiness"] is None
    assert report.ambiguous_count == 1


def test_unknown_scale_is_invalid() -> None:
    report = ScaleExtractionReport()
    out = resolve_score_fields(
        {"happiness": 5, "happiness_scale": "bogus"},
        report=report,
    )
    assert out["happiness"] is None
    assert report.invalid_count == 1


def test_null_scale_falls_through_to_missing_without_legacy() -> None:
    with pytest.raises(MeasurementScaleMissing):
        resolve_measurement("happiness", {"happiness": 5, "happiness_scale": None})


def test_legacy_lifeos_adapter_by_source_uri() -> None:
    resolved = resolve_measurement(
        "happiness",
        {"happiness": 5},
        event_type="life.daily_check_in.completed.v1",
        source_ids=["lifemaxxxing://daily-check-ins/42"],
    )
    assert resolved.declared_scale is MeasurementScale.LIKERT_1_10
    assert resolved.scale_source.value == "legacy_adapter"
    assert abs(resolved.normalized_value - (4.0 / 9.0 * 100.0)) < 1e-9


def test_legacy_lifeos_rejects_0_100_magnitude_without_explicit() -> None:
    """Synthetic 62 without scale under LifeOS URI → out of range for 1_10."""
    report = ScaleExtractionReport()
    out = resolve_score_fields(
        {"happiness": 62},
        event_type="life.daily_check_in.completed.v1",
        source_ids=["lifemaxxxing://daily-check-ins/99"],
        report=report,
    )
    assert out["happiness"] is None
    assert report.invalid_count == 1


def test_string_value_invalid() -> None:
    report = ScaleExtractionReport()
    out = resolve_score_fields(
        {"happiness": "high", "happiness_scale": "0_100"},
        report=report,
    )
    assert out["happiness"] is None
    assert report.invalid_count == 1


def test_unknown_scale_raises_on_direct_resolve() -> None:
    with pytest.raises(MeasurementScaleUnknown):
        resolve_measurement(
            "stress",
            {"stress": 3, "stress_scale": "likert_0_7"},
        )


class _Row:
    def __init__(self, *, happ: float, scale: str | None, source: str, pos: int = 1) -> None:
        from datetime import datetime, UTC

        self.domain_pack = "life"
        self.subject = "daily_check_in"
        self.metadata = {
            "life_event_type": "life.daily_check_in.completed.v1",
            "observation_purpose": "USER_OBSERVATION",
            "subject_scope": "PERSONAL",
        }
        self.occurred_at = datetime(2026, 7, 10, tzinfo=UTC)
        self.global_position = pos
        self.observation_id = f"obs-{pos}"
        self.source_ids = [source]
        attrs: dict = {"happiness": happ, "stress": 4, "energy": 7, "productivity": 7}
        if scale:
            attrs["happiness_scale"] = scale
            attrs["stress_scale"] = scale
            attrs["energy_scale"] = scale
            attrs["productivity_scale"] = scale
            attrs["measurement_contract_version"] = MEASUREMENT_CONTRACT_VERSION
        self.context = {"attributes": attrs, "environment": "PRODUCTION"}


def test_extract_preserves_5_on_0_100() -> None:
    days = extract_checkin_days(
        [
            _Row(
                happ=5,
                scale="0_100",
                source="synthetic://test/1",
            )
        ]
    )
    assert len(days) == 1
    assert days[0].happiness == 5.0


def test_extract_preserves_10_on_0_100() -> None:
    days = extract_checkin_days(
        [_Row(happ=10, scale="0_100", source="synthetic://test/2")]
    )
    assert days[0].happiness == 10.0


def test_no_productive_magnitude_inference_ast() -> None:
    """Structural gate: productive modules must not infer scale via raw <= 10."""
    roots = [
        Path("src/intelligence_maxxxing/domain_packs/life/wellbeing_v1.py"),
        Path("src/intelligence_maxxxing/domain_packs/life/measurement_scale.py"),
        Path("src/intelligence_maxxxing/domain_packs/life/wellbeing_v2/features.py"),
        Path("src/intelligence_maxxxing/domain_packs/life/wellbeing_v2/observations.py"),
    ]
    for path in roots:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                # flag: x <= 10 used near scale decisions
                for comparator in node.comparators:
                    if isinstance(comparator, ast.Constant) and comparator.value == 10:
                        # Allow unrelated comparisons only if not with raw/value names
                        left = node.left
                        if isinstance(left, ast.Name) and left.id in {"raw", "value", "v", "score"}:
                            raise AssertionError(
                                f"magnitude-style compare in {path}:{node.lineno}"
                            )
            if isinstance(node, ast.FunctionDef) and node.name == "_to_score_100":
                raise AssertionError(f"_to_score_100 must not exist in {path}")


def test_normalization_version_constant() -> None:
    assert NORMALIZATION_VERSION == "canonical_0_100_v1"
    assert MEASUREMENT_CONTRACT_VERSION == "wellbeing_measurements_v1"
