"""Stage 3 epistemic E2E canaries (synthetic data only).

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


def _params() -> dict:
    return {
        "sleep_threshold_hours": 7.0,
        "minimum_meaningful_difference": 0.5,
        "prospective_target": 14,
        "maximum_window_days": 60,
    }


def _checkin(
    *,
    secret: str,
    occurred_at: datetime,
    sleep_hours: float,
    productivity: float,
) -> None:
    body = {
        "schema_version": "1.0",
        "domain_pack": "life",
        "subject": "daily_check_in",
        "statement": "synthetic stage3 check-in",
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
        "source_ids": [],
        "metadata": {"life_event_type": "life.daily_check_in.completed.v1", "synthetic": True},
        "occurred_at": occurred_at.isoformat(),
    }
    r = eng("POST", "/api/v1/observations", secret, body, {"Idempotency-Key": _idem()})
    ok("seed observation", r.status_code in (200, 201), r.text[:200])


def _seed_association(secret: str, start: datetime, days: int, *, positive: bool) -> None:
    """Seed balanced groups around threshold 7.0 with a clear productivity gap."""
    for i in range(days):
        day = start + timedelta(days=i)
        if i % 2 == 0:
            sleep = 8.0
            prod = 8.5 if positive else 3.0
        else:
            sleep = 5.5
            prod = 3.0 if positive else 8.5
        _checkin(secret=secret, occurred_at=day, sleep_hours=sleep, productivity=prod)


def run_online() -> None:
    life_secret = os.environ["E2E_LIFE_CREDENTIAL"]
    other_secret = os.environ["E2E_OTHER_CREDENTIAL"]

    # --- Canary 1: insufficient evidence ---
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
    ev = eng(
        "POST",
        f"/api/v1/experiments/{exp1}/evaluate",
        life_secret,
        {"phase": "BASELINE_EXPLORATORY"},
        {"Idempotency-Key": _idem()},
    )
    ok("c1 evaluate", ev.status_code == 201, ev.text[:200])
    ok("c1 insufficient", ev.json()["data"]["belief_state"] == "INSUFFICIENT_EVIDENCE")

    # --- Canary 2: exploratory positive ---
    # Seed BEFORE activation so observations fall into the baseline window.
    past = datetime.now(UTC) - timedelta(days=40)
    _seed_association(life_secret, past, 16, positive=True)
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
        {"parameters": _params()},
        {"Idempotency-Key": _idem()},
    )
    exp2 = act2.json()["data"]["experiment_id"]
    ev2 = eng(
        "POST",
        f"/api/v1/experiments/{exp2}/evaluate",
        life_secret,
        {"phase": "BASELINE_EXPLORATORY"},
        {"Idempotency-Key": _idem()},
    )
    ok("c2 evaluate", ev2.status_code == 201, ev2.text[:200])
    state2 = ev2.json()["data"]["belief_state"]
    ok("c2 exploratory positive", state2 == "EXPLORATORY_POSITIVE", state2)
    ok("c2 never prospective supported on baseline", state2 != "PROSPECTIVE_SUPPORTED")

    # --- Canary 3: prospective supported ---
    # Seed AFTER activation into the prospective window.
    now = datetime.now(UTC)
    _seed_association(life_secret, now - timedelta(minutes=1), 16, positive=True)
    ev3 = eng(
        "POST",
        f"/api/v1/experiments/{exp2}/evaluate",
        life_secret,
        {"phase": "PROSPECTIVE_VALIDATION"},
        {"Idempotency-Key": _idem()},
    )
    ok("c3 evaluate", ev3.status_code == 201, ev3.text[:200])
    state3 = ev3.json()["data"]["belief_state"]
    ok("c3 prospective supported", state3 == "PROSPECTIVE_SUPPORTED", state3)
    bel = eng("GET", f"/api/v1/hypotheses/{hyp2}/beliefs/current", life_secret)
    ok("c3 belief readable", bel.status_code == 200 and bel.json()["data"] is not None)
    bdata = bel.json()["data"]
    ok("c3 calibration UNCALIBRATED", bdata["calibration_state"] == "UNCALIBRATED")
    ok("c3 causality CORRELATION", bdata["causality_level"] == "CORRELATION")

    # --- Canary 4: contradiction / weakened ---
    past4 = datetime.now(UTC) - timedelta(days=40)
    _seed_association(life_secret, past4, 16, positive=True)
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
        {"parameters": _params()},
        {"Idempotency-Key": _idem()},
    )
    exp4 = act4.json()["data"]["experiment_id"]
    eng(
        "POST",
        f"/api/v1/experiments/{exp4}/evaluate",
        life_secret,
        {"phase": "BASELINE_EXPLORATORY"},
        {"Idempotency-Key": _idem()},
    )
    _seed_association(life_secret, datetime.now(UTC) - timedelta(minutes=1), 40, positive=False)
    ev4 = eng(
        "POST",
        f"/api/v1/experiments/{exp4}/evaluate",
        life_secret,
        {"phase": "PROSPECTIVE_VALIDATION"},
        {"Idempotency-Key": _idem()},
    )
    ok("c4 evaluate", ev4.status_code == 201, ev4.text[:200])
    state4 = ev4.json()["data"]["belief_state"]
    ok(
        "c4 contradiction path",
        state4 in {"PROSPECTIVE_WEAKENED", "PROSPECTIVE_INCONCLUSIVE"},
        state4,
    )
    learn = eng("GET", f"/api/v1/hypotheses/{hyp4}/learning", life_secret)
    ok("c4 learning recorded", learn.status_code == 200 and len(learn.json()["data"]["items"]) >= 1)

    # --- Canary 5: isolation ---
    other = eng("GET", f"/api/v1/hypotheses/{hyp2}", other_secret)
    ok("c5 isolation", other.status_code in (403, 404), str(other.status_code))

    # --- Canary 6: replay ---
    key = _idem()
    first = eng(
        "POST",
        "/api/v1/hypotheses",
        life_secret,
        {"human_confirmed": False},
        {"Idempotency-Key": key},
    )
    second = eng(
        "POST",
        "/api/v1/hypotheses",
        life_secret,
        {"human_confirmed": False},
        {"Idempotency-Key": key},
    )
    ok("c6 first create", first.status_code == 201)
    ok("c6 replay", second.status_code == 200 and second.json()["data"]["replayed"] is True)

    # --- Life BFF smoke ---
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
    print(f"Stage 3 epistemic canaries phase={PHASE}")
    if PHASE == "offline":
        run_offline()
    else:
        run_online()
    print(f"ALL STAGE 3 CANARIES PASSED ({len(_passed)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
