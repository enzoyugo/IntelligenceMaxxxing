"""Observation extraction for wellbeing_v2 (Life check-ins + optional attrs).

Score fields are normalized once to canonical 0–100 via the measurement scale
contract (no magnitude inference).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from intelligence_maxxxing.domain_packs.life.exclusion_registry import exclusion_id_set
from intelligence_maxxxing.domain_packs.life.input_selection import (
    SelectionReport,
    select_effective_observations,
)
from intelligence_maxxxing.domain_packs.life.measurement_scale import (
    ScaleExtractionReport,
    resolve_score_fields,
)

LIFE_EVENT_TYPE = "life.daily_check_in.completed.v1"
WORKOUT_EVENT_TYPE = "life.workout.completed.v1"


@dataclass(frozen=True)
class DayRecord:
    day: date
    happiness: float | None
    stress: float | None
    energy: float | None
    productivity: float | None
    sleep_hours: float | None
    gym_done: bool | None
    social_activity: bool | None
    alcohol: bool | None
    meetings_count: float | None
    workout_done: bool | None
    global_position: int
    observed_fields: tuple[str, ...]


def _attrs(row: Any) -> dict[str, Any]:
    ctx = row.context if isinstance(getattr(row, "context", None), dict) else {}
    attrs = ctx.get("attributes")
    return attrs if isinstance(attrs, dict) else {}


def _f(attrs: dict[str, Any], key: str) -> float | None:
    raw = attrs.get(key)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _b(attrs: dict[str, Any], key: str) -> bool | None:
    raw = attrs.get(key)
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str):
        return raw.lower() in {"1", "true", "yes"}
    return None


def _day(occurred: Any) -> date | None:
    if isinstance(occurred, datetime):
        return occurred.date()
    return None


def extract_day_records(
    rows: list[Any],
    *,
    report: ScaleExtractionReport | None = None,
    selection_report: SelectionReport | None = None,
) -> list[DayRecord]:
    """First-write (lowest global_position) daily check-ins; merge workout flags.

    Happiness/stress/energy/productivity are stored as canonical 0–100.
    Applies the same wellbeing_input_selection_v1 filter as V1.
    """
    checkins: dict[date, DayRecord] = {}
    workouts: set[date] = set()
    scale_report = report or ScaleExtractionReport()
    effective, sel = select_effective_observations(rows, exclusion_ids=exclusion_id_set())
    if selection_report is not None:
        selection_report.included = sel.included
        selection_report.decisions = sel.decisions

    ordered = sorted(
        effective,
        key=lambda r: (int(getattr(r, "global_position", 0)), getattr(r, "observation_id", "")),
    )
    for row in ordered:
        if getattr(row, "domain_pack", None) != "life":
            continue
        meta = row.metadata if isinstance(getattr(row, "metadata", None), dict) else {}
        event = meta.get("life_event_type")
        day = _day(getattr(row, "occurred_at", None))
        if day is None:
            continue
        if event == WORKOUT_EVENT_TYPE or getattr(row, "subject", None) == "workout":
            workouts.add(day)
            continue
        if getattr(row, "subject", None) != "daily_check_in":
            continue
        if event != LIFE_EVENT_TYPE:
            continue
        if day in checkins:
            continue
        attrs = _attrs(row)
        source_ids = list(getattr(row, "source_ids", None) or [])
        scores = resolve_score_fields(
            attrs,
            event_type=LIFE_EVENT_TYPE,
            source_ids=source_ids,
            metadata=meta,
            report=scale_report,
        )
        observed: list[str] = []
        for key in (
            "happiness",
            "stress",
            "energy",
            "productivity",
            "sleep_hours",
            "gym_done",
            "social_activity",
            "alcohol",
            "meetings_count",
        ):
            if key in scores and scores[key] is not None:
                observed.append(key)
            elif key not in scores and attrs.get(key) is not None:
                observed.append(key)
        checkins[day] = DayRecord(
            day=day,
            happiness=scores["happiness"],
            stress=scores["stress"],
            energy=scores["energy"],
            productivity=scores["productivity"],
            sleep_hours=_f(attrs, "sleep_hours"),
            gym_done=_b(attrs, "gym_done"),
            social_activity=_b(attrs, "social_activity"),
            alcohol=_b(attrs, "alcohol"),
            meetings_count=_f(attrs, "meetings_count"),
            workout_done=None,
            global_position=int(getattr(row, "global_position", 0)),
            observed_fields=tuple(observed),
        )

    out: list[DayRecord] = []
    for day, rec in sorted(checkins.items(), key=lambda x: x[0]):
        workout = True if day in workouts or rec.gym_done else (False if rec.gym_done is False else None)
        if day in workouts and rec.gym_done is None:
            workout = True
        out.append(
            DayRecord(
                day=rec.day,
                happiness=rec.happiness,
                stress=rec.stress,
                energy=rec.energy,
                productivity=rec.productivity,
                sleep_hours=rec.sleep_hours,
                gym_done=rec.gym_done,
                social_activity=rec.social_activity,
                alcohol=rec.alcohol,
                meetings_count=rec.meetings_count,
                workout_done=workout,
                global_position=rec.global_position,
                observed_fields=rec.observed_fields,
            )
        )
    return out
