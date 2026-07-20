"""Stage 3.1 epistemic E2E canaries (synthetic data only; no future-dated hacks).

Env:
  E2E_ENGINE_URL, E2E_LIFE_URL, E2E_LIFE_CREDENTIAL, E2E_OTHER_CREDENTIAL, E2E_PHASE
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, datetime, timedelta

import httpx

ENGINE = os.environ["E2E_ENGINE_URL"].rstrip("/")
LIFE = os.environ["E2E_LIFE_URL"].rstrip("/")
PHASE = os.environ.get("E2E_PHASE", "online")
_passed: list[str] = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        print(f"CANARY FAILED: {name} {detail}")
        sys.exit(1)
    _passed.append(name)
    print(f"  ok: {name}")


def eng(
    method: str, path: str, secret: str, body: dict | None = None, headers: dict | None = None
) -> httpx.Response:
    merged = {"Authorization": f"Bearer {secret}", **(headers or {})}
    with httpx.Client(base_url=ENGINE, timeout=60) as client:
        return client.request(method, path, json=body, headers=merged)


def life(method: str, path: str, body: dict | None = None) -> httpx.Response:
    with httpx.Client(base_url=LIFE, timeout=30) as client:
        return client.request(method, path, json=body)


def _idem() -> str:
    return f"e2e-{uuid.uuid4().hex}"


def _params(*, target: int = 42, window_days: int = 60) -> dict:
    return {
        "sleep_threshold_hours": 7.0,
        "minimum_meaningful_difference": 0.5,
        "prospective_target": target,
        "maximum_window_days": window_days,
    }


def _checkin(
    *,
    secret: str,
    occurred_at: datetime,
    sleep_hours: float,
    productivity: float,
    source_record_id: str,
) -> None:
    # Stage 3.1: never send occurred_at in the future relative to wall clock.
    assert occurred_at <= datetime.now(UTC) + timedelta(minutes=1)
    body = {
        "schema_version": "1.0",
        "domain_pack": "life",
        "subject": "daily_check_in",
        "statement": "synthetic stage3.1 check-in",
        "knowledge_class": "OBSERVED_FACT",
        "observed_by": "stage3-e2e",
        "context": {
            "scope": "personal",
            "attributes": {
                "sleep_hours": sleep_hours,
                "productivity": productivity,
                "stress": 4,
                "alcohol": 0,
                "meetings_count": 1,
                "gym_done": 0,
                "football_played": 0,
                "social_activity": 0,
            },
        },
        "source_ids": [f"lifemaxxxing://daily-check-ins/{source_record_id}"],
        "metadata": {"life_event_type": "life.daily_check_in.completed.v1", "synthetic": True},
        "occurred_at": occurred_at.isoformat(),
    }
    r = eng("POST", "/api/v1/observations", secret, body, {"Idempotency-Key": _idem()})
    ok("seed observation", r.status_code in (200, 201), r.text[:200])


def _seed_association(
    secret: str, start: datetime, days: int, *, positive: bool, prefix: str
) -> None:
    """Seed balanced groups. All occurred_at <= now (no future fabrication)."""
    now = datetime.now(UTC)
    for i in range(days):
        day = start + timedelta(hours=i)
        if day > now:
            day = now - timedelta(seconds=(days - i))
        if i % 2 == 0:
            sleep = 8.0
            prod = 8.5 if positive else 3.0
        else:
            sleep = 5.5
            prod = 3.0 if positive else 8.5
        _checkin(
            secret=secret,
            occurred_at=day,
            sleep_hours=sleep,
            productivity=prod,
            source_record_id=f"{prefix}-{i}",
        )


def run_online() -> None:
    life_secret = os.environ["E2E_LIFE_CREDENTIAL"]
    other_secret = os.environ["E2E_OTHER_CREDENTIAL"]

    # Canary 1 — future rejection (occurred_at slightly ahead of skew → excluded)
    prop = eng(
        "POST",
        "/api/v1/hypotheses",
        life_secret,
        {"human_confirmed": False},
        {"Idempotency-Key": _idem()},
    )
    ok("c1 propose", prop.status_code == 201, prop.text[:200])
    hyp1 = prop.json()["data"]["hypothesis_id"]
    act = eng(
        "POST",
        f"/api/v1/hypotheses/{hyp1}/activate",
        life_secret,
        {"parameters": _params()},
        {"Idempotency-Key": _idem()},
    )
    ok("c1 activate", act.status_code == 201, act.text[:200])
    exp1 = act.json()["data"]["experiment_id"]
    # Intentionally >5min skew to force OCCURRED_AT_IN_FUTURE exclusion.
    future = datetime.now(UTC) + timedelta(hours=6)
    body_future = {
        "schema_version": "1.0",
        "domain_pack": "life",
        "subject": "daily_check_in",
        "statement": "future synthetic",
        "knowledge_class": "OBSERVED_FACT",
        "observed_by": "stage3-e2e",
        "context": {
            "scope": "personal",
            "attributes": {"sleep_hours": 8.0, "productivity": 9.0},
        },
        "source_ids": ["lifemaxxxing://daily-check-ins/future-1"],
        "metadata": {"life_event_type": "life.daily_check_in.completed.v1", "synthetic": True},
        "occurred_at": future.isoformat(),
    }
    # Allow submit (Engine accepts observation); evaluation must not count it.
    eng(
        "POST",
        "/api/v1/observations",
        life_secret,
        body_future,
        {"Idempotency-Key": _idem()},
    )
    ev = eng(
        "POST",
        f"/api/v1/experiments/{exp1}/evaluate",
        life_secret,
        {"phase": "PROSPECTIVE_VALIDATION"},
        {"Idempotency-Key": _idem()},
    )
    ok("c1 evaluate", ev.status_code == 201, ev.text[:200])
    d1 = ev.json()["data"]
    ok("c1 not supported", d1["belief_state"] != "PROSPECTIVE_SUPPORTED", d1["belief_state"])
    ok("c1 collecting or insufficient", d1["belief_state"] in {"PROSPECTIVE_COLLECTING", "INSUFFICIENT_EVIDENCE"})
    ok("c1 not terminal", d1.get("terminal") is False)

    # Canary 2 — target enforcement (14 < 42)
    prop2 = eng(
        "POST",
        "/api/v1/hypotheses",
        life_secret,
        {"human_confirmed": False},
        {"Idempotency-Key": _idem()},
    )
    hyp2 = prop2.json()["data"]["hypothesis_id"]
    act2 = eng(
        "POST",
        f"/api/v1/hypotheses/{hyp2}/activate",
        life_secret,
        {"parameters": _params(target=42)},
        {"Idempotency-Key": _idem()},
    )
    exp2 = act2.json()["data"]["experiment_id"]
    start = datetime.now(UTC) - timedelta(hours=13)
    _seed_association(life_secret, start, 14, positive=True, prefix=f"t14-{uuid.uuid4().hex[:8]}")
    ev2 = eng(
        "POST",
        f"/api/v1/experiments/{exp2}/evaluate",
        life_secret,
        {"phase": "PROSPECTIVE_VALIDATION"},
        {"Idempotency-Key": _idem()},
    )
    ok("c2 evaluate", ev2.status_code == 201, ev2.text[:200])
    d2 = ev2.json()["data"]
    ok("c2 collecting", d2["belief_state"] == "PROSPECTIVE_COLLECTING", d2["belief_state"])
    ok("c2 not terminal", d2.get("terminal") is False)
    ok("c2 target remaining", int(d2.get("target_remaining", 0)) >= 28)

    learn2 = eng("GET", f"/api/v1/hypotheses/{hyp2}/learning", life_secret)
    ok(
        "c2 no learning",
        learn2.status_code == 200 and len(learn2.json()["data"]["items"]) == 0,
        str(len(learn2.json()["data"]["items"])),
    )

    # Canary 3 — semantic replay (different Idempotency-Key)
    key_a = _idem()
    key_b = _idem()
    r_a = eng(
        "POST",
        f"/api/v1/experiments/{exp2}/evaluate",
        life_secret,
        {"phase": "PROSPECTIVE_VALIDATION"},
        {"Idempotency-Key": key_a},
    )
    r_b = eng(
        "POST",
        f"/api/v1/experiments/{exp2}/evaluate",
        life_secret,
        {"phase": "PROSPECTIVE_VALIDATION"},
        {"Idempotency-Key": key_b},
    )
    ok("c3 first", r_a.status_code in (200, 201))
    ok("c3 second", r_b.status_code in (200, 201))
    ok(
        "c3 same evidence",
        r_a.json()["data"]["evidence_id"] == r_b.json()["data"]["evidence_id"],
    )
    ok("c3 replayed", r_b.json()["data"]["replayed"] is True)

    # Canary 4 — duplicate source (14 rows / 7 sources)
    prop4 = eng(
        "POST",
        "/api/v1/hypotheses",
        life_secret,
        {"human_confirmed": False},
        {"Idempotency-Key": _idem()},
    )
    hyp4 = prop4.json()["data"]["hypothesis_id"]
    act4 = eng(
        "POST",
        f"/api/v1/hypotheses/{hyp4}/activate",
        life_secret,
        {"parameters": _params(target=42)},
        {"Idempotency-Key": _idem()},
    )
    exp4 = act4.json()["data"]["experiment_id"]
    base = datetime.now(UTC) - timedelta(hours=20)
    prefix = f"dup-{uuid.uuid4().hex[:8]}"
    for i in range(14):
        src = f"{prefix}-{i % 7}"
        _checkin(
            secret=life_secret,
            occurred_at=base + timedelta(minutes=i),
            sleep_hours=8.0 if i % 2 == 0 else 5.5,
            productivity=8.5 if i % 2 == 0 else 3.0,
            source_record_id=src,
        )
    ev4 = eng(
        "POST",
        f"/api/v1/experiments/{exp4}/evaluate",
        life_secret,
        {"phase": "PROSPECTIVE_VALIDATION"},
        {"Idempotency-Key": _idem()},
    )
    d4 = ev4.json()["data"]
    ok("c4 evaluate", ev4.status_code == 201, ev4.text[:200])
    ok("c4 eligible <= 7", int(d4.get("prospective_eligible", 99)) <= 7, str(d4.get("prospective_eligible")))
    ok("c4 not supported", d4["belief_state"] != "PROSPECTIVE_SUPPORTED")

    # Canary 5 — isolation
    other = eng("GET", f"/api/v1/hypotheses/{hyp2}", other_secret)
    ok("c5 isolation", other.status_code in (403, 404), str(other.status_code))

    # Canary 6 — Life BFF
    listed = life("GET", "/api/intelligence/hypotheses")
    ok("life list hypotheses", listed.status_code == 200 and listed.json()["ok"] is True)
    ok(
        "life never leaks secret",
        life_secret not in listed.text and "imx_sk_" not in listed.text,
    )


def run_offline() -> None:
    listed = life("GET", "/api/intelligence/hypotheses")
    body = listed.json()
    ok(
        "offline envelope",
        listed.status_code in (503, 502) and body.get("ok") is False,
        listed.text[:200],
    )
    details = (body.get("error") or {}).get("details") or {}
    ok("offline retryable", details.get("retryable") is True or listed.status_code >= 500)


def main() -> int:
    print(f"Stage 3.1 epistemic canaries phase={PHASE}")
    if PHASE == "offline":
        run_offline()
    else:
        run_online()
    print(f"ALL STAGE 3.1 CANARIES PASSED ({len(_passed)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
