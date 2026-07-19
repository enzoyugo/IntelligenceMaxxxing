"""Stage 2 cross-repo E2E canaries: LifeMaxxxing backend <-> Engine over real HTTP.

Driven by scripts/audit/run_lifemaxxxing_contract_gates.ps1. Requires env:
  E2E_ENGINE_URL       e.g. http://127.0.0.1:8110
  E2E_LIFE_URL         e.g. http://127.0.0.1:8011
  E2E_LIFE_CREDENTIAL  the LifeMaxxxing application secret (read-only checks)
  E2E_OTHER_CREDENTIAL a second application's secret (isolation check)
  E2E_PHASE            "online" or "offline"

Exit code 0 = all canaries in the phase passed.
"""

from __future__ import annotations

import json
import os
import sys
import uuid

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


def life(method: str, path: str, body: dict | None = None) -> httpx.Response:
    with httpx.Client(base_url=LIFE, timeout=15) as client:
        return client.request(method, path, json=body)


def engine_get(path: str, secret: str) -> httpx.Response:
    with httpx.Client(base_url=ENGINE, timeout=15) as client:
        return client.get(path, headers={"Authorization": f"Bearer {secret}"})


def checkin_payload() -> dict:
    return {
        "date": "2026-07-19",
        "happiness": 8,
        "energy": 7,
        "stress": 3,
        "productivity": 9,
        "sleep_hours": 7.5,
        "gym_done": True,
        "alcohol": False,
        "deep_work_blocks": 4,
        "meetings_count": 1,
        # These MUST be stripped before the Engine sees the observation:
        "notes": "PRIVATE-JOURNAL-TEXT-CANARY",
        "main_work_win": "PRIVATE-WIN-CANARY",
        "main_blocker": "PRIVATE-BLOCKER-CANARY",
    }


def run_online() -> None:
    life_secret = os.environ["E2E_LIFE_CREDENTIAL"]
    other_secret = os.environ["E2E_OTHER_CREDENTIAL"]

    # 1. Life backend is healthy and the intelligence status is fully configured.
    health = life("GET", "/health")
    ok("life backend health", health.status_code == 200)

    status = life("GET", "/api/intelligence/status")
    body = status.json()
    ok("status envelope ok", status.status_code == 200 and body["ok"] is True)
    data = body["data"]
    ok("status enabled+configured", data["enabled"] and data["configured"])
    ok("status engine reachable", data["reachable"] is True)
    ok(
        "status never leaks the secret",
        life_secret not in status.text and "imx_sk_" not in status.text,
    )

    # 2. Daily check-in canary: full round trip with receipt.
    idem = f"e2e-checkin-{uuid.uuid4().hex}"
    sync = life(
        "POST",
        "/api/intelligence/observations/sync",
        {
            "event_type": "life.daily_check_in.completed.v1",
            "idempotency_key": idem,
            "payload": checkin_payload(),
        },
    )
    receipt = sync.json()["data"]
    ok("check-in accepted", sync.status_code == 200 and sync.json()["ok"] is True)
    ok(
        "receipt has ids",
        receipt["observation_id"].startswith("obs_")
        and receipt["event_id"].startswith("evt_")
        and receipt["audit_id"].startswith("aud_"),
    )
    ok("first submit is not a replay", receipt["replayed"] is False)

    # 3. Replay canary: same idempotency key does NOT duplicate.
    replay = life(
        "POST",
        "/api/intelligence/observations/sync",
        {
            "event_type": "life.daily_check_in.completed.v1",
            "idempotency_key": idem,
            "payload": checkin_payload(),
        },
    )
    rec2 = replay.json()["data"]
    ok("replay flagged", rec2["replayed"] is True)
    ok("replay same observation", rec2["observation_id"] == receipt["observation_id"])

    # 4. Data minimization canary: the Engine stored NO free text.
    obs = engine_get(f"/api/v1/observations/{receipt['observation_id']}", life_secret)
    obs_body = obs.json()
    ok("engine returns the observation", obs.status_code == 200 and obs_body["ok"] is True)
    obs_text = json.dumps(obs_body)
    ok("no journal text reached the engine", "PRIVATE-JOURNAL-TEXT-CANARY" not in obs_text)
    ok("no win/blocker text reached the engine", "PRIVATE-WIN-CANARY" not in obs_text)
    attributes = obs_body["data"]["context"].get("attributes", {})
    ok("structured metrics did arrive", attributes.get("happiness") == 8.0)
    ok("life domain pack", obs_body["data"]["domain_pack"] == "life")

    # 5. Workout canary.
    widem = f"e2e-workout-{uuid.uuid4().hex}"
    workout = life(
        "POST",
        "/api/intelligence/observations/sync",
        {
            "event_type": "life.workout.completed.v1",
            "idempotency_key": widem,
            "payload": {
                "type": "push",
                "duration_minutes": 70,
                "intensity": 8,
                "exercise_count": 5,
                "total_sets": 18,
                "total_volume_kg": 3200.5,
                "notes": "PRIVATE-WORKOUT-NOTES-CANARY",
            },
        },
    )
    wreceipt = workout.json()["data"]
    ok("workout accepted", workout.status_code == 200)
    wobs = engine_get(f"/api/v1/observations/{wreceipt['observation_id']}", life_secret)
    ok("workout free text stayed local", "PRIVATE-WORKOUT-NOTES-CANARY" not in wobs.text)
    ok(
        "workout type preserved",
        wobs.json()["data"]["context"]["attributes"].get("type") == "push",
    )

    # 6. Audit recoverability THROUGH the Life backend (not direct-from-app).
    audit = life("GET", f"/api/intelligence/audits/{receipt['audit_id']}")
    audit_body = audit.json()
    ok("audit retrievable via life backend", audit.status_code == 200 and audit_body["ok"])
    ok("audit id round-trips", audit_body["data"]["audit_id"] == receipt["audit_id"])
    ok(
        "audit references the observation",
        receipt["observation_id"] in audit_body["data"]["output_object_ids"],
    )

    # 7. Unknown event type is rejected with a typed 422 (nothing reaches the Engine).
    bad = life(
        "POST",
        "/api/intelligence/observations/sync",
        {
            "event_type": "life.unregistered.v1",
            "idempotency_key": f"e2e-bad-{uuid.uuid4().hex}",
            "payload": {},
        },
    )
    ok("unknown event type rejected", bad.status_code == 422)
    ok("unknown event typed code", bad.json()["error"]["code"] == "unknown_event_type")

    # 8. Idempotency conflict is typed (same key, different payload).
    conflict = life(
        "POST",
        "/api/intelligence/observations/sync",
        {
            "event_type": "life.daily_check_in.completed.v1",
            "idempotency_key": idem,
            "payload": {**checkin_payload(), "happiness": 1},
        },
    )
    ok("idempotency conflict is 409", conflict.status_code == 409)
    ok("conflict typed code", conflict.json()["error"]["code"] == "engine_conflict")

    # 9. Application isolation: ANOTHER app's credential cannot read Life's audit.
    other_audit = engine_get(f"/api/v1/audits/{receipt['audit_id']}", other_secret)
    ok("cross-app audit read denied", other_audit.status_code == 404)
    own_audit = engine_get(f"/api/v1/audits/{receipt['audit_id']}", life_secret)
    ok("own audit read allowed", own_audit.status_code == 200)

    print(f"ONLINE CANARIES PASSED ({len(_passed)})")


def run_offline() -> None:
    # Engine is DOWN. The Life backend must stay healthy and answer typed errors.
    health = life("GET", "/health")
    ok("life backend still healthy with engine down", health.status_code == 200)

    status = life("GET", "/api/intelligence/status")
    ok("status still served", status.status_code == 200)
    ok("status reports unreachable", status.json()["data"]["reachable"] is False)

    sync = life(
        "POST",
        "/api/intelligence/observations/sync",
        {
            "event_type": "life.daily_check_in.completed.v1",
            "idempotency_key": f"e2e-offline-{uuid.uuid4().hex}",
            "payload": checkin_payload(),
        },
    )
    ok("offline sync returns 503", sync.status_code == 503)
    err = sync.json()["error"]
    ok("offline error is retryable", err["details"]["retryable"] is True)
    ok("offline error typed", err["code"] in {"engine_unreachable", "engine_unavailable"})

    print(f"OFFLINE CANARIES PASSED ({len(_passed)})")


if __name__ == "__main__":
    if PHASE == "offline":
        run_offline()
    else:
        run_online()
