"""Canary for isolated wellbeing scale + input-selection smoke.

Runs against ISO_ENGINE_URL with ISO_ENGINE_SECRET. Writes only to the temp DB
backing that Engine. Never uses production credentials.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx


def _fail(msg: str) -> None:
    print(f"CANARY FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    base = os.environ.get("ISO_ENGINE_URL", "").rstrip("/")
    secret = os.environ.get("ISO_ENGINE_SECRET", "")
    artifact_dir = Path(os.environ.get("ISO_ARTIFACT_DIR", "."))
    if not base or not secret:
        _fail("ISO_ENGINE_URL / ISO_ENGINE_SECRET required")
    if "8100" in base:
        _fail("refusing production-looking port 8100")

    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "X-Request-Id": f"iso-{uuid.uuid4().hex[:12]}",
    }

    day = datetime.now(UTC).strftime("%Y-%m-%d")
    test_subject = f"test-{uuid.uuid4().hex}"
    source_id = f"lifemaxxxing://daily-check-ins/smoke-E2E_SCALE_CONTRACT_V1-{day}-iso"

    # 1) TEST purpose on PRODUCTION environment must be rejected (422).
    reject_body = {
        "schema_version": "1.0",
        "domain_pack": "life",
        "subject": "daily_check_in",
        "statement": "Daily check-in completed",
        "knowledge_class": "OBSERVED_FACT",
        "observed_by": "iso-smoke",
        "context": {
            "scope": "personal",
            "environment": "PRODUCTION",
            "attributes": {
                "happiness": 5,
                "happiness_scale": "0_100",
                "stress": 10,
                "stress_scale": "0_100",
                "energy": 50,
                "energy_scale": "0_100",
                "productivity": 50,
                "productivity_scale": "0_100",
                "measurement_contract_version": "wellbeing_measurements_v1",
            },
        },
        "source_ids": [source_id + "-reject"],
        "metadata": {
            "life_event_type": "life.daily_check_in.completed.v1",
            "observation_purpose": "SMOKE_TEST",
            "subject_scope": "TEST_PROFILE",
            "test_run_id": test_subject,
        },
        "occurred_at": f"{day}T19:15:00+00:00",
    }
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            f"{base}/api/v1/observations",
            headers={**headers, "Idempotency-Key": f"iso-reject-{uuid.uuid4().hex}"},
            json=reject_body,
        )
        if r.status_code not in (400, 422):
            _fail(f"expected reject of SMOKE_TEST on PRODUCTION, got {r.status_code}: {r.text}")

        # 2) Proper TEST environment observation accepted.
        ok_body = dict(reject_body)
        ok_body["context"] = {
            **reject_body["context"],
            "environment": "TEST",
        }
        ok_body["source_ids"] = [source_id]
        idem = f"iso-accept-{uuid.uuid4().hex}"
        r2 = client.post(
            f"{base}/api/v1/observations",
            headers={**headers, "Idempotency-Key": idem},
            json=ok_body,
        )
        if r2.status_code != 200:
            _fail(f"TEST observation submit failed: {r2.status_code} {r2.text}")
        data = r2.json()["data"]
        obs_id = data["observation_id"]

        r3 = client.post(
            f"{base}/api/v1/observations",
            headers={**headers, "Idempotency-Key": idem},
            json=ok_body,
        )
        if r3.status_code != 200 or not r3.json()["data"].get("replayed"):
            _fail("idempotent replay failed")

        # 3) Personal USER observation (production purpose) for baseline day.
        user_body = {
            "schema_version": "1.0",
            "domain_pack": "life",
            "subject": "daily_check_in",
            "statement": "Daily check-in completed",
            "knowledge_class": "OBSERVED_FACT",
            "observed_by": "iso-smoke",
            "context": {
                "scope": "personal",
                "environment": "PRODUCTION",
                "attributes": {
                    "happiness": 8,
                    "happiness_scale": "1_10",
                    "stress": 3,
                    "stress_scale": "1_10",
                    "energy": 7,
                    "energy_scale": "1_10",
                    "productivity": 7,
                    "productivity_scale": "1_10",
                    "measurement_contract_version": "wellbeing_measurements_v1",
                },
            },
            "source_ids": [f"lifemaxxxing://daily-check-ins/{test_subject}-user"],
            "metadata": {
                "life_event_type": "life.daily_check_in.completed.v1",
                "observation_purpose": "USER_OBSERVATION",
                "subject_scope": "PERSONAL",
            },
            "occurred_at": f"{day}T20:00:00+00:00",
        }
        r4 = client.post(
            f"{base}/api/v1/observations",
            headers={**headers, "Idempotency-Key": f"iso-user-{uuid.uuid4().hex}"},
            json=user_body,
        )
        if r4.status_code != 200:
            _fail(f"user observation failed: {r4.status_code} {r4.text}")

        v1 = client.get(
            f"{base}/api/v1/wellbeing/current",
            headers=headers,
            params={"window_days": 14, "formula_id": "wellbeing_v1"},
        )
        if v1.status_code != 200:
            _fail(f"wellbeing v1 failed: {v1.status_code} {v1.text}")
        snap = v1.json()["data"]["snapshot"]
        feats = snap.get("features") or {}

        if snap.get("formula_version") != "1.2":
            _fail(f"expected wellbeing_v1@1.2 got {snap.get('formula_version')}")
        if feats.get("input_selection_policy_version") != "wellbeing_input_selection_v1":
            _fail("missing input_selection_policy_version")
        if int(feats.get("excluded_test_count") or 0) < 1:
            _fail("expected excluded_test_count >= 1")
        if int(snap.get("sample_size") or 0) != 1:
            _fail(f"expected sample_size=1 got {snap.get('sample_size')}")

        v2 = client.get(
            f"{base}/api/v1/wellbeing/current",
            headers=headers,
            params={"window_days": 14, "formula_id": "wellbeing_v2"},
        )
        if v2.status_code != 200:
            _fail(f"wellbeing v2 failed: {v2.status_code} {v2.text}")
        snap2 = v2.json()["data"]["snapshot"]
        if snap2.get("formula_version") != "2.1.0":
            _fail("expected wellbeing_v2@2.1.0")
        if snap2.get("formula_status") != "SHADOW":
            _fail("V2 must remain SHADOW")

    report = {
        "temp_observation_id": obs_id,
        "test_run_id": test_subject,
        "environment": "TEST",
        "purpose": "SMOKE_TEST",
        "engine_url": base,
        "v1_sample_size": snap.get("sample_size"),
        "excluded_test_count": feats.get("excluded_test_count"),
        "input_selection_policy_version": feats.get("input_selection_policy_version"),
        "production_ledger_writes": False,
    }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "canary_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print("CANARY PASS", json.dumps(report))


if __name__ == "__main__":
    main()
