"""Generate new V1/V2 snapshots against the live Engine (does not print secrets)."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx


def _load_lifeos_cred() -> tuple[str, str]:
    base = os.environ.get("ENGINE_BASE_URL", "http://127.0.0.1:8100").rstrip("/")
    secret = os.environ.get("INTELLIGENCE_ENGINE_CREDENTIAL", "")
    if secret:
        return base, secret
    # Read LifeOS server env without printing values.
    candidates = [
        Path(r"C:\Users\AORUS\lifeos-maxxxing\.env.server"),
        Path(r"C:\Users\AORUS\lifeos-maxxxing\.env"),
    ]
    vals: dict[str, str] = {}
    for path in candidates:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip().strip('"').strip("'")
    base = vals.get("INTELLIGENCE_ENGINE_BASE_URL", base).rstrip("/")
    secret = vals.get("INTELLIGENCE_ENGINE_CREDENTIAL", "")
    if not secret:
        raise SystemExit("missing INTELLIGENCE_ENGINE_CREDENTIAL")
    return base, secret


def main() -> int:
    base, secret = _load_lifeos_cred()
    headers = {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}
    out: dict = {"generated_at": datetime.now(UTC).isoformat(), "engine_base": base}
    with httpx.Client(timeout=60.0) as client:
        live = client.get(f"{base}/health/live")
        if live.status_code != 200:
            print(f"engine not live: {live.status_code}", file=sys.stderr)
            return 1
        for fid in ("wellbeing_v1", "wellbeing_v2"):
            r = client.get(
                f"{base}/api/v1/wellbeing/current",
                headers=headers,
                params={"window_days": 14, "formula_id": fid},
            )
            if r.status_code not in (200, 201):
                print(f"{fid} failed: {r.status_code} {r.text[:300]}", file=sys.stderr)
                return 1
            snap = r.json()["data"]["snapshot"]
            feats = snap.get("features") or {}
            out[fid] = {
                "score_snapshot_id": snap.get("score_snapshot_id"),
                "formula_id": snap.get("formula_id"),
                "formula_version": snap.get("formula_version"),
                "formula_status": snap.get("formula_status"),
                "happiness": snap.get("happiness"),
                "stress": snap.get("stress"),
                "confidence": snap.get("confidence"),
                "sample_size": snap.get("sample_size"),
                "data_sufficiency": snap.get("data_sufficiency"),
                "change_state": snap.get("change_state"),
                "input_fingerprint": snap.get("input_fingerprint"),
                "input_selection_policy_version": feats.get("input_selection_policy_version"),
                "included_observation_count": feats.get("included_observation_count"),
                "excluded_test_count": feats.get("excluded_test_count"),
                "excluded_invalidated_count": feats.get("excluded_invalidated_count"),
                "excluded_ambiguous_count": feats.get("excluded_ambiguous_count"),
                "computed_at": snap.get("computed_at"),
            }
    path = Path("artifacts/isolation_closeout/new_effective_snapshots.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    # Print redacted summary only.
    print(
        json.dumps(
            {
                "wrote": str(path),
                "v1": out["wellbeing_v1"],
                "v2": out["wellbeing_v2"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
