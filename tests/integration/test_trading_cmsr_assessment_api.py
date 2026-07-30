"""HTTP integration for CMSR assessment API."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from intelligence_maxxxing.api.app import create_app
from intelligence_maxxxing.config import EngineSettings
from intelligence_maxxxing.domain_packs.trading.cmsr_validate_v1 import (
    CMSR_ASSESSMENT_SCHEMA_VERSION,
    schema_file_hash,
    validate_cmsr_assessment,
)


BRIDGE_TOKEN = "test-token"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("IM_TRADING_STORE_DIR", str(tmp_path / "store"))
    monkeypatch.setenv("IM_TRADING_BRIDGE_TOKEN", BRIDGE_TOKEN)
    monkeypatch.setenv("ENGINE_ENV", "test")
    settings = EngineSettings(
        ENGINE_ENV="test",
        DATABASE_URL=f"sqlite+pysqlite:///{tmp_path / 't.db'}",
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def _request() -> dict:
    decision_time = "2026-07-21T12:00:00Z"
    raw_setup = {
        "setup_id": "setup_cmsr_im_http_001",
        "strategy_id": "GPTS_OWN_PROPFIRM_KILLER_V1",
        "symbol": "EURUSD",
        "direction": "LONG",
        "decision_time": decision_time,
        "available_at": decision_time,
        "entry": 1.0910,
        "stop": 1.0890,
        "target": 1.0950,
    }
    from intelligence_maxxxing.domain_packs.trading.cmsr_validate_v1 import content_hash, raw_setup_hash

    setup_hash = raw_setup_hash(raw_setup)
    factors = [
        {
            "factor_id": "cross_market_confirmation",
            "state": "AVAILABLE_CONFIRMED",
            "value": {"aligned": True, "components": 6},
            "confidence": 0.88,
            "available_at": decision_time,
            "observed_at": decision_time,
            "source_timestamp": decision_time,
            "classification": "DERIVED",
        },
        {
            "factor_id": "uncertainty",
            "state": "AVAILABLE",
            "value": {"score": 0.2},
            "confidence": 0.8,
            "available_at": decision_time,
            "observed_at": decision_time,
            "source_timestamp": decision_time,
            "classification": "DERIVED",
        },
    ]
    snap = {
        "schema_version": "trader_view_snapshot.v3",
        "snapshot_id": "snap_cmsr_im_http_001",
        "snapshot_hash": content_hash({"factors": factors}),
        "profile_id": "CMSR_V1",
        "decision_time": decision_time,
        "readiness": {"readiness": "READY", "economic_take_permitted": True},
        "factors": factors,
    }
    return {
        "schema_version": "tmx.im.cmsr.assessment.request.v1",
        "request_id": "req_cmsr_im_http_001",
        "experiment_id": "TMX_IM_CMSR_TM_PLUS_IM_V1",
        "setup_id": raw_setup["setup_id"],
        "raw_setup_hash": setup_hash,
        "strategy_id": raw_setup["strategy_id"],
        "decision_time": decision_time,
        "available_at_utc": decision_time,
        "idempotency_key": "CMSR_IDEM_im_http_001",
        "trader_view_snapshot": snap,
        "raw_setup": raw_setup,
        "provenance": {"source_system": "TradingMaxxxing", "research_only": True},
    }


def test_cmsr_schema_parity_hashes() -> None:
    assert schema_file_hash("tmx.im.cmsr.assessment.request.v1.json") == (
        "6824145b12e25cb4404e3e26705c769bf5f1d2af68dd25454f093f4fc51d04ba"
    )
    assert schema_file_hash("im.tmx.cmsr.assessment.v1.json") == (
        "b5f0d73db865fda50d068ba961f5e5e36e1f411100b62c444ed0a4179f40cdfa"
    )


def test_cmsr_assess_idempotent(client: TestClient) -> None:
    req = _request()
    headers = {
        "X-Trading-Bridge-Token": BRIDGE_TOKEN,
        "Idempotency-Key": req["idempotency_key"],
    }
    first = client.post("/api/v1/trading/cmsr-assessments", json=req, headers=headers)
    assert first.status_code == 201
    body = first.json()
    assert body["ok"] is True
    assert body["data"]["schema_version"] == CMSR_ASSESSMENT_SCHEMA_VERSION
    assert validate_cmsr_assessment(body["data"])["ok"] is True
    aid = body["data"]["assessment_id"]
    second = client.post("/api/v1/trading/cmsr-assessments", json=req, headers=headers)
    assert second.status_code == 201
    assert second.json()["data"]["assessment_id"] == aid
    got = client.get(
        f"/api/v1/trading/cmsr-assessments/{aid}",
        headers={"X-Trading-Bridge-Token": BRIDGE_TOKEN},
    )
    assert got.status_code == 200


def test_cmsr_rejects_outcome_leakage(client: TestClient) -> None:
    req = _request()
    bad = deepcopy(req)
    bad["outcome"] = {"realized_R": 1.0}
    resp = client.post(
        "/api/v1/trading/cmsr-assessments",
        json=bad,
        headers={"X-Trading-Bridge-Token": BRIDGE_TOKEN},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] in {"CMSR_REQUEST_INVALID", "CAUSALITY_BLOCK"}


def test_cmsr_rejects_future_available_at(client: TestClient) -> None:
    req = _request()
    bad = deepcopy(req)
    bad["trader_view_snapshot"]["factors"][0]["available_at"] = "2099-01-01T00:00:00Z"
    resp = client.post(
        "/api/v1/trading/cmsr-assessments",
        json=bad,
        headers={"X-Trading-Bridge-Token": BRIDGE_TOKEN},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "CAUSALITY_BLOCK"
