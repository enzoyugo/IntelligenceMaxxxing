"""Stage 3.1 temporal eligibility rules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from intelligence_maxxxing.domain_packs.life.eligibility import (
    select_eligible_checkins,
    split_by_temporal_anchors,
)
from intelligence_maxxxing.domain_packs.life.methods.bayesian_bootstrap import classify_belief_state


def _row(
    *,
    oid: str,
    pos: int,
    occurred: datetime,
    recorded: datetime,
    source: str,
    sleep: float = 8.0,
    prod: float = 8.0,
) -> SimpleNamespace:
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
        occurred_at=occurred,
        created_at=recorded,
        global_position=pos,
    )


def test_future_occurred_at_not_eligible() -> None:
    act = datetime(2026, 7, 1, tzinfo=UTC)
    eval_at = datetime(2026, 7, 10, tzinfo=UTC)
    future = eval_at + timedelta(days=2)
    el = select_eligible_checkins(
        [
            _row(
                oid="1",
                pos=10,
                occurred=future,
                recorded=eval_at,
                source="lifemaxxxing://daily-check-ins/d1",
            )
        ],
        tenant_id="t1",
        owner_id="o1",
        application_id="a1",
    )
    _, prospective, excl = split_by_temporal_anchors(
        el.eligible,
        baseline_cutoff=act,
        prospective_start=act,
        activation_global_position=5,
        activation_recorded_at=act,
        evidence_cutoff_global_position=100,
        evidence_cutoff_recorded_at=eval_at,
        evaluation_started_at=eval_at,
    )
    assert prospective == []
    assert excl.get("OCCURRED_AT_IN_FUTURE", 0) == 1


def test_backdated_post_activation_not_in_baseline() -> None:
    act = datetime(2026, 7, 10, tzinfo=UTC)
    old_day = datetime(2026, 7, 1, tzinfo=UTC)
    el = select_eligible_checkins(
        [
            _row(
                oid="1",
                pos=20,
                occurred=old_day,
                recorded=act + timedelta(hours=1),
                source="lifemaxxxing://daily-check-ins/d1",
            )
        ],
        tenant_id="t1",
        owner_id="o1",
        application_id="a1",
    )
    baseline, _, excl = split_by_temporal_anchors(
        el.eligible,
        baseline_cutoff=act,
        prospective_start=act,
        activation_global_position=10,
        activation_recorded_at=act,
        evidence_cutoff_global_position=100,
        evidence_cutoff_recorded_at=act + timedelta(days=1),
        evaluation_started_at=act + timedelta(days=1),
    )
    assert baseline == []
    assert excl.get("BACKFILLED_AFTER_ACTIVATION", 0) == 1


def test_target_42_with_14_remains_collecting() -> None:
    state = classify_belief_state(
        phase="PROSPECTIVE_VALIDATION",
        n_sufficient=7,
        n_below=7,
        p_delta_gt_0=0.99,
        p_delta_ge_mmd=0.99,
        ci90_low=1.0,
        prospective_target=42,
        expired=False,
    )
    assert state == "PROSPECTIVE_COLLECTING"


def test_strong_effect_cannot_bypass_target() -> None:
    state = classify_belief_state(
        phase="PROSPECTIVE_VALIDATION",
        n_sufficient=20,
        n_below=20,
        p_delta_gt_0=0.999,
        p_delta_ge_mmd=0.999,
        ci90_low=2.0,
        prospective_target=42,
        expired=False,
    )
    # 40 < 42 → still collecting despite strong effect
    assert state == "PROSPECTIVE_COLLECTING"


def test_deadline_incomplete_expires_inconclusive() -> None:
    state = classify_belief_state(
        phase="PROSPECTIVE_VALIDATION",
        n_sufficient=7,
        n_below=7,
        p_delta_gt_0=0.99,
        p_delta_ge_mmd=0.99,
        ci90_low=1.0,
        prospective_target=42,
        expired=True,
    )
    assert state == "EXPIRED_INCONCLUSIVE"
