"""HTTP integration for generic strategy assessment API."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from intelligence_maxxxing.api.app import create_app
from intelligence_maxxxing.config import EngineSettings
from intelligence_maxxxing.domain_packs.trading.strategy_assessment_validate_v1 import (
    STRATEGY_ASSESSMENT_SCHEMA_VERSION,
    validate_strategy_assessment,
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
    signal_time = "2026-07-21T12:00:00Z"
    return {
        "schema_version": "tmx.im.strategy.assessment.request.v1",
        "request_id": "req_strat_im_http_001",
        "run_id": "run_strat_im_http_001",
        "raw_setup_id": "setup_strat_im_http_001",
        "idempotency_key": "STRAT_IDEM_im_http_001",
        "strategy": {
            "strategy_id": "LONDON_NY_BREAKOUT",
            "strategy_version": "1.0.0",
            "family": "LONDON_NY_BREAKOUT",
            "profile_version": "1.0.0",
        },
        "market": {
            "market": "FX",
            "symbol": "GBPUSD",
            "timeframe": "M5",
            "signal_time": signal_time,
            "available_at": signal_time,
        },
        "setup": {
            "direction": "LONG",
            "entry": 1.2710,
            "stop": 1.2690,
            "target": 1.2750,
        },
        "trader_view": {
            "snapshot_version": "trader_view_snapshot.v3",
            "factor_states": [
                {
                    "factor_id": "session_context",
                    "status": "AVAILABLE_HIGH",
                    "value": "OVERLAP",
                    "confidence": 0.92,
                    "available_at": signal_time,
                    "strategy_criticality": "REQUIRED",
                },
                {
                    "factor_id": "geometry_valid",
                    "status": "AVAILABLE_HIGH",
                    "value": True,
                    "confidence": 0.95,
                    "available_at": signal_time,
                    "strategy_criticality": "REQUIRED",
                },
                {
                    "factor_id": "cost_burden",
                    "status": "AVAILABLE_HIGH",
                    "value": 0.06,
                    "confidence": 0.88,
                    "available_at": signal_time,
                    "strategy_criticality": "REQUIRED",
                },
            ],
        },
        "costs": {
            "scenario_id": "C0_LOT_BASED_COMMISSION_RECONSTRUCTED",
            "commission_r": 0.06,
        },
        "lineage": {"source_system": "TradingMaxxxing", "research_only": True},
    }


def test_strategy_assess_idempotent(client: TestClient) -> None:
    req = _request()
    headers = {
        "X-Trading-Bridge-Token": BRIDGE_TOKEN,
        "Idempotency-Key": req["idempotency_key"],
    }
    first = client.post("/api/v1/trading/strategy-assessments", json=req, headers=headers)
    assert first.status_code == 201
    body = first.json()
    assert body["ok"] is True
    assert body["data"]["schema_version"] == STRATEGY_ASSESSMENT_SCHEMA_VERSION
    assert body["data"]["decision"] == "TAKE"
    assert validate_strategy_assessment(body["data"])["ok"] is True
    aid = body["data"]["assessment_id"]
    second = client.post("/api/v1/trading/strategy-assessments", json=req, headers=headers)
    assert second.status_code == 201
    assert second.json()["data"]["assessment_id"] == aid
    got = client.get(
        f"/api/v1/trading/strategy-assessments/{aid}",
        headers={"X-Trading-Bridge-Token": BRIDGE_TOKEN},
    )
    assert got.status_code == 200


def test_strategy_rejects_outcome_leakage(client: TestClient) -> None:
    req = _request()
    bad = deepcopy(req)
    bad["realized_R"] = 1.0
    resp = client.post(
        "/api/v1/trading/strategy-assessments",
        json=bad,
        headers={"X-Trading-Bridge-Token": BRIDGE_TOKEN},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] in {"STRATEGY_REQUEST_INVALID", "CAUSALITY_BLOCK"}


def test_strategy_rejects_future_available_at(client: TestClient) -> None:
    req = _request()
    bad = deepcopy(req)
    bad["trader_view"]["factor_states"][0]["available_at"] = "2099-01-01T00:00:00Z"
    resp = client.post(
        "/api/v1/trading/strategy-assessments",
        json=bad,
        headers={"X-Trading-Bridge-Token": BRIDGE_TOKEN},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "CAUSALITY_BLOCK"
