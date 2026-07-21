"""HTTP integration for trading assessment API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from intelligence_maxxxing.api.app import create_app
from intelligence_maxxxing.config import EngineSettings


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("IM_TRADING_STORE_DIR", str(tmp_path / "store"))
    monkeypatch.setenv("IM_TRADING_BRIDGE_TOKEN", "tmx-im-local-bridge-v1")
    monkeypatch.setenv("ENGINE_ENV", "test")
    settings = EngineSettings(
        ENGINE_ENV="test",
        DATABASE_URL=f"sqlite+pysqlite:///{tmp_path / 't.db'}",
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def _obs():
    return {
        "schema_version": "tmx.im.observation.v1",
        "experiment_id": "TMX_IM_TRIPLE_LANE_PROSPECTIVE_V1",
        "observation_id": "OBS_HTTP_1",
        "idempotency_key": "IDEM_HTTP_1",
        "source_system": "TradingMaxxxing",
        "source_commit": "abc",
        "created_at_utc": "2026-07-21T01:00:00Z",
        "decision_cutoff_utc": "2026-07-21T01:00:00Z",
        "available_at_utc": "2026-07-21T01:00:00Z",
        "economic_setup": {
            "economic_setup_id": "ES_HTTP",
            "source_event_id": "E1",
            "strategy_id": "s14_shadow",
            "strategy_family": "S14",
            "strategy_implementation_version": "v1",
            "strategy_fidelity_class": "PROXY",
            "symbol": "EURUSD",
            "timeframe": "M5",
            "direction": "LONG",
            "signal_time_utc": "2026-07-21T01:00:00Z",
            "order_type": "STOP",
            "entry": 1.1,
            "stop": 1.09,
            "target": 1.12,
            "setup_geometry_hash": "g",
            "config_hash": "c",
            "nominal_risk_R": 1.0,
        },
        "raw_strategy": {
            "decision": "TAKE",
            "reason_codes": ["SOURCE"],
            "nominal_risk_R": 1.0,
            "decision_created_at_utc": "2026-07-21T01:00:00Z",
        },
        "tmx_native": {
            "decision": "UNKNOWN",
            "reason_codes": ["SHADOW"],
            "nominal_risk_R": 1.0,
            "decision_created_at_utc": "2026-07-21T01:00:00Z",
        },
        "feature_snapshot_id": "FS_HTTP",
        "features": {},
        "market_context": {"symbol": "EURUSD"},
        "data_quality": {"quote_quality": "QUOTE_VALID", "cost_quality": "COST_UNAVAILABLE"},
        "risk_context": {},
        "portfolio_context": {},
        "provenance": {},
    }


def test_health_and_policy(client: TestClient) -> None:
    h = client.get(
        "/api/v1/trading/health",
        headers={"X-Trading-Bridge-Token": "tmx-im-local-bridge-v1"},
    )
    assert h.status_code == 200
    assert h.json()["ok"] is True
    p = client.get(
        "/api/v1/trading/policies/active",
        headers={"X-Trading-Bridge-Token": "tmx-im-local-bridge-v1"},
    )
    assert p.status_code == 200
    assert p.json()["data"]["policy_version"] == "1.0.0"


def test_assess_idempotent(client: TestClient) -> None:
    headers = {
        "X-Trading-Bridge-Token": "tmx-im-local-bridge-v1",
        "Idempotency-Key": "IDEM_HTTP_1",
    }
    a = client.post("/api/v1/trading/assessments", json=_obs(), headers=headers)
    assert a.status_code == 201
    aid = a.json()["data"]["assessment_id"]
    b = client.post("/api/v1/trading/assessments", json=_obs(), headers=headers)
    assert b.status_code == 201
    assert b.json()["data"]["assessment_id"] == aid
    g = client.get(
        f"/api/v1/trading/assessments/{aid}",
        headers={"X-Trading-Bridge-Token": "tmx-im-local-bridge-v1"},
    )
    assert g.status_code == 200
