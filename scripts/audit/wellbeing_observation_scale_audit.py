#!/usr/bin/env python3
"""Classify wellbeing check-in observations by scale resolution class.

Classes:
  EXPLICIT_SCALE — per-field *_scale present and valid
  KNOWN_LEGACY_CONTRACT — no explicit scale; legacy adapter resolves
  AMBIGUOUS — no explicit scale and no known legacy policy
  INVALID — scale/value violates contract (unknown scale, out of range, …)

Does not rewrite historical events. heuristic_only / not_authoritative for
magnitude guesses — never used here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from intelligence_maxxxing.domain_packs.life.measurement_scale import (  # noqa: E402
    MeasurementScaleError,
    MeasurementScaleMissing,
    SCORE_FIELDS,
    resolve_field_scale,
    resolve_measurement,
)

LIFE_EVENT = "life.daily_check_in.completed.v1"


def classify_attrs(
    attrs: dict[str, Any],
    *,
    event_type: str = LIFE_EVENT,
    source_ids: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    present = [f for f in SCORE_FIELDS if attrs.get(f) is not None]
    if not present:
        return "AMBIGUOUS"
    classes: set[str] = set()
    for field in present:
        try:
            scale, source = resolve_field_scale(
                field,
                attrs,
                event_type=event_type,
                source_ids=source_ids,
                metadata=metadata,
            )
            resolve_measurement(
                field,
                attrs,
                event_type=event_type,
                source_ids=source_ids,
                metadata=metadata,
            )
            if source.value == "explicit_field":
                classes.add("EXPLICIT_SCALE")
            else:
                classes.add("KNOWN_LEGACY_CONTRACT")
            _ = scale
        except MeasurementScaleMissing:
            classes.add("AMBIGUOUS")
        except MeasurementScaleError:
            classes.add("INVALID")
    if "INVALID" in classes:
        return "INVALID"
    if "AMBIGUOUS" in classes:
        return "AMBIGUOUS"
    if classes == {"EXPLICIT_SCALE"}:
        return "EXPLICIT_SCALE"
    if "KNOWN_LEGACY_CONTRACT" in classes and "EXPLICIT_SCALE" not in classes:
        return "KNOWN_LEGACY_CONTRACT"
    if "EXPLICIT_SCALE" in classes and "KNOWN_LEGACY_CONTRACT" in classes:
        return "EXPLICIT_SCALE"  # mixed resolution still has explicit coverage
    return "AMBIGUOUS"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        help="JSONL of {attributes, source_ids?, metadata?, event_type?}",
    )
    parser.add_argument("--demo", action="store_true", help="Run built-in demo cases")
    args = parser.parse_args()

    cases: list[dict[str, Any]] = []
    if args.demo or not args.input:
        cases = [
            {
                "label": "explicit_0_100",
                "attributes": {
                    "happiness": 5,
                    "happiness_scale": "0_100",
                    "stress": 10,
                    "stress_scale": "0_100",
                },
            },
            {
                "label": "lifeos_legacy_uri",
                "attributes": {"happiness": 7, "stress": 4},
                "source_ids": ["lifemaxxxing://daily-check-ins/1"],
            },
            {
                "label": "ambiguous_bare",
                "attributes": {"happiness": 5, "stress": 10},
            },
            {
                "label": "invalid_range_under_legacy",
                "attributes": {"happiness": 62},
                "source_ids": ["lifemaxxxing://daily-check-ins/2"],
            },
        ]
    else:
        for line in args.input.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    summary = {"EXPLICIT_SCALE": 0, "KNOWN_LEGACY_CONTRACT": 0, "AMBIGUOUS": 0, "INVALID": 0}
    rows = []
    for case in cases:
        attrs = case.get("attributes") or case.get("attrs") or {}
        klass = classify_attrs(
            attrs,
            event_type=case.get("event_type", LIFE_EVENT),
            source_ids=case.get("source_ids"),
            metadata=case.get("metadata"),
        )
        summary[klass] += 1
        rows.append({"label": case.get("label"), "class": klass})

    print(json.dumps({"summary": summary, "rows": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
