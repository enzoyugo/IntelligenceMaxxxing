"""Wellbeing input selection — test observations cannot capture personal days."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from intelligence_maxxxing.domain_packs.life.exclusion_registry import exclusion_id_set
from intelligence_maxxxing.domain_packs.life.input_selection import (
    INPUT_SELECTION_POLICY_VERSION,
    SelectionDecision,
    classify_for_personal_production,
    select_effective_observations,
)
from intelligence_maxxxing.domain_packs.life.wellbeing_v1 import (
    compute_wellbeing_v1,
    extract_checkin_days,
)


def _row(
    *,
    oid: str,
    pos: int,
    day_offset: int = 0,
    happ: float = 7.0,
    stress: float = 4.0,
    source: str | None = "lifemaxxxing://daily-check-ins/42",
    purpose: str | None = "USER_OBSERVATION",
    environment: str | None = "PRODUCTION",
    subject_scope: str | None = "PERSONAL",
    scales: str = "1_10",
) -> SimpleNamespace:
    base = datetime(2026, 7, 10, 12, 0, tzinfo=UTC) + timedelta(days=day_offset)
    attrs = {
        "happiness": happ,
        "stress": stress,
        "energy": 7.0,
        "productivity": 7.0,
        "happiness_scale": scales,
        "stress_scale": scales,
        "energy_scale": scales,
        "productivity_scale": scales,
        "measurement_contract_version": "wellbeing_measurements_v1",
    }
    meta: dict = {"life_event_type": "life.daily_check_in.completed.v1"}
    if purpose:
        meta["observation_purpose"] = purpose
    if subject_scope:
        meta["subject_scope"] = subject_scope
    ctx: dict = {"attributes": attrs, "scope": "life"}
    if environment:
        ctx["environment"] = environment
    return SimpleNamespace(
        domain_pack="life",
        subject="daily_check_in",
        metadata=meta,
        occurred_at=base,
        global_position=pos,
        observation_id=oid,
        source_ids=[source] if source else [],
        context=ctx,
    )


def test_policy_version_constant() -> None:
    assert INPUT_SELECTION_POLICY_VERSION == "wellbeing_input_selection_v1"


def test_local_e2e_activation_cohort_excluded() -> None:
    row = _row(
        oid="obs_local_e2e_act",
        pos=1,
        source="lifemaxxxing://daily-check-ins/local-E2E_WELLBEING_ACTIVATION_2026-07-16",
        purpose=None,
        environment=None,
        scales="0_100",
        happ=62,
        stress=40,
    )
    assert classify_for_personal_production(row) is SelectionDecision.EXCLUDED_TEST


def test_known_smoke_observation_excluded() -> None:
    row = _row(
        oid="obs_ab746ef9d6c64732990a6e7fc4aaea15",
        pos=1,
        source="lifemaxxxing://daily-check-ins/smoke-E2E_SCALE_CONTRACT_V1-2026-07-21",
        purpose=None,
        environment=None,
        scales="0_100",
        happ=5,
        stress=10,
    )
    assert classify_for_personal_production(row) is SelectionDecision.EXCLUDED_TEST
    assert row.observation_id in exclusion_id_set()


def test_case_a_smoke_before_user_same_day() -> None:
    smoke = _row(
        oid="obs_smoke1",
        pos=1,
        source="lifemaxxxing://daily-check-ins/smoke-E2E_SCALE_CONTRACT_V1-d",
        purpose="SMOKE_TEST",
        environment="TEST",
        scales="0_100",
        happ=5,
        stress=10,
    )
    user = _row(oid="obs_user1", pos=2, happ=8.0, stress=3.0)
    days = extract_checkin_days([smoke, user])
    assert len(days) == 1
    # User Likert 8 → canonical ~77.78
    assert days[0].happiness is not None and days[0].happiness > 70
    result = compute_wellbeing_v1(days, window_days=14, as_of=days[0].day)
    assert result.sample_size == 1


def test_case_b_user_before_smoke_same_day() -> None:
    user = _row(oid="obs_user2", pos=1, happ=8.0, stress=3.0)
    smoke = _row(
        oid="obs_smoke2",
        pos=2,
        source="lifemaxxxing://daily-check-ins/smoke-E2E_SCALE_CONTRACT_V1-d2",
        purpose="SMOKE_TEST",
        environment="TEST",
        scales="0_100",
        happ=5,
        stress=10,
    )
    a = extract_checkin_days([user])
    b = extract_checkin_days([user, smoke])
    assert a[0].happiness == b[0].happiness
    assert a[0].stress == b[0].stress
    ra = compute_wellbeing_v1(a, window_days=14, as_of=a[0].day)
    rb = compute_wellbeing_v1(b, window_days=14, as_of=b[0].day)
    assert ra.happiness == rb.happiness
    assert ra.stress == rb.stress
    assert ra.confidence == rb.confidence
    assert ra.sample_size == rb.sample_size == 1


def test_case_c_only_smokes_no_personal_day() -> None:
    smokes = [
        _row(
            oid=f"obs_s{i}",
            pos=i,
            day_offset=i,
            source=f"lifemaxxxing://daily-check-ins/smoke-E2E_SCALE_CONTRACT_V1-{i}",
            purpose="SMOKE_TEST",
            environment="TEST",
            scales="0_100",
            happ=5,
            stress=10,
        )
        for i in range(2)
    ]
    days = extract_checkin_days(smokes)
    assert days == []


def test_case_d_ambiguous_bare_excluded() -> None:
    bare = _row(
        oid="obs_bare",
        pos=1,
        source=None,
        purpose=None,
        environment=None,
        subject_scope=None,
    )
    bare.source_ids = []
    assert classify_for_personal_production(bare) is SelectionDecision.EXCLUDED_AMBIGUOUS
    assert extract_checkin_days([bare]) == []


def test_case_e_test_profile_separated() -> None:
    personal = _row(oid="obs_p", pos=1, happ=8.0)
    test_subj = _row(
        oid="obs_t",
        pos=2,
        happ=1.0,
        stress=10.0,
        subject_scope="TEST_PROFILE",
        purpose="SMOKE_TEST",
        environment="TEST",
        source="lifemaxxxing://daily-check-ins/test-profile-1",
    )
    days = extract_checkin_days([personal, test_subj])
    assert len(days) == 1
    assert days[0].happiness is not None and days[0].happiness > 70


def test_fingerprint_invariance_adding_test() -> None:
    users = [_row(oid=f"u{i}", pos=i + 1, day_offset=i, happ=7.0, stress=4.0) for i in range(5)]
    smoke = _row(
        oid="obs_extra_smoke",
        pos=99,
        day_offset=2,
        source="lifemaxxxing://daily-check-ins/smoke-E2E_SCALE_CONTRACT_V1-x",
        purpose="SMOKE_TEST",
        environment="TEST",
        scales="0_100",
        happ=5,
        stress=10,
    )
    d0 = extract_checkin_days(users)
    d1 = extract_checkin_days([*users, smoke])
    r0 = compute_wellbeing_v1(d0, window_days=14, as_of=d0[-1].day)
    r1 = compute_wellbeing_v1(d1, window_days=14, as_of=d1[-1].day)
    assert r0.happiness == r1.happiness
    assert r0.stress == r1.stress
    assert r0.confidence == r1.confidence
    assert r0.sample_size == r1.sample_size


def test_selection_report_counts() -> None:
    user = _row(oid="obs_u", pos=1)
    smoke = _row(
        oid="obs_ab746ef9d6c64732990a6e7fc4aaea15",
        pos=2,
        source="lifemaxxxing://daily-check-ins/smoke-E2E_SCALE_CONTRACT_V1-z",
        purpose=None,
        environment=None,
    )
    included, report = select_effective_observations([user, smoke])
    assert len(included) == 1
    assert report.excluded_test_count >= 1
    feats = report.as_features()
    assert feats["input_selection_policy_version"] == INPUT_SELECTION_POLICY_VERSION
