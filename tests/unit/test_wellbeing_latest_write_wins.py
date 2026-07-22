"""Same-day edits: latest selected observation wins for V1/V2 extraction."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from intelligence_maxxxing.domain_packs.life.wellbeing_v1 import extract_checkin_days
from intelligence_maxxxing.domain_packs.life.wellbeing_v2.observations import (
    extract_day_records,
)


def _row(pos: int, happ: float, stress: float, oid: str) -> SimpleNamespace:
    return SimpleNamespace(
        observation_id=oid,
        global_position=pos,
        domain_pack="life",
        subject="daily_check_in",
        occurred_at=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
        source_ids=[f"lifemaxxxing://daily-check-ins/2026-07-21"],
        metadata={
            "life_event_type": "life.daily_check_in.completed.v1",
            "observation_purpose": "USER_OBSERVATION",
            "observation_environment": "PRODUCTION",
        },
        context={
            "schema_version": "1.0",
            "scope": "personal",
            "environment": "PRODUCTION",
            "attributes": {
                "happiness": happ,
                "stress": stress,
                "energy": 7.0,
                "productivity": 9.0,
                "sleep_hours": 9.0,
                "gym_done": True,
                "happiness_scale": "1_10",
                "stress_scale": "1_10",
                "energy_scale": "1_10",
                "productivity_scale": "1_10",
                "measurement_contract_version": "wellbeing_measurements_v1",
            },
        },
    )


def test_v1_latest_write_wins_same_calendar_day() -> None:
    rows = [
        _row(17, 5.0, 8.0, "obs_old"),
        _row(18, 7.0, 5.0, "obs_new"),
    ]
    days = extract_checkin_days(rows)
    assert len(days) == 1
    # 1_10 → 0–100 via (n-1)/9*100; latest row (pos 18) wins over pos 17.
    assert days[0].happiness == pytest.approx(66.66666666666666)
    assert days[0].stress == pytest.approx(44.44444444444444)
    assert days[0].global_position == 18


def test_v2_shares_latest_write_wins() -> None:
    rows = [
        _row(17, 5.0, 8.0, "obs_old"),
        _row(18, 7.0, 5.0, "obs_new"),
    ]
    days = extract_day_records(rows)
    assert len(days) == 1
    assert days[0].happiness == pytest.approx(66.66666666666666)
    assert days[0].stress == pytest.approx(44.44444444444444)
    assert days[0].global_position == 18
