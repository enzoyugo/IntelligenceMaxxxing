"""Stage 3.1 logical source identity deduplication."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from intelligence_maxxxing.domain_packs.life.eligibility import select_eligible_checkins


def _row(
    oid: str,
    pos: int,
    source: str,
    *,
    sleep: float = 8.0,
    prod: float = 7.0,
    occurred: datetime | None = None,
) -> SimpleNamespace:
    when = occurred or datetime(2026, 7, 5, tzinfo=UTC)
    return SimpleNamespace(
        observation_id=oid,
        event_id=f"evt_{oid}",
        tenant_id="t1",
        owner_id="o1",
        application_id="a1",
        domain_pack="life",
        subject="daily_check_in",
        knowledge_class="OBSERVED_FACT",
        metadata={"life_event_type": "life.daily_check_in.completed.v1"},
        context={"attributes": {"sleep_hours": sleep, "productivity": prod}},
        source_ids=(source,),
        occurred_at=when,
        created_at=when,
        global_position=pos,
    )


def test_same_source_id_counted_once() -> None:
    src = "lifemaxxxing://daily-check-ins/day-1"
    result = select_eligible_checkins(
        [_row("a", 2, src), _row("b", 5, src)],
        tenant_id="t1",
        owner_id="o1",
        application_id="a1",
    )
    assert len(result.eligible) == 1
    assert result.eligible[0].observation_id == "a"
    assert result.exclusion_reasons.get("DUPLICATE_LOGICAL_SOURCE") == 1


def test_observation_id_is_not_logical_dedup_key() -> None:
    # Different observation_ids, same source → one eligible
    result = select_eligible_checkins(
        [
            _row("obs1", 1, "lifemaxxxing://daily-check-ins/x"),
            _row("obs2", 2, "lifemaxxxing://daily-check-ins/x"),
        ],
        tenant_id="t1",
        owner_id="o1",
        application_id="a1",
    )
    assert len(result.eligible) == 1


def test_source_id_format_required() -> None:
    bad = _row("a", 1, "not-a-canonical-source")
    result = select_eligible_checkins([bad], tenant_id="t1", owner_id="o1", application_id="a1")
    assert result.eligible == []
    assert result.exclusion_reasons.get("SOURCE_ID_FORMAT_REQUIRED") == 1


def test_duplicate_source_with_conflict_blocks_support() -> None:
    src = "lifemaxxxing://daily-check-ins/conflict"
    result = select_eligible_checkins(
        [_row("a", 1, src, sleep=8.0, prod=8.0), _row("b", 2, src, sleep=5.0, prod=3.0)],
        tenant_id="t1",
        owner_id="o1",
        application_id="a1",
    )
    assert result.critical_data_quality_failure is True
    assert result.exclusion_reasons.get("DUPLICATE_SOURCE_CONFLICT") == 1
