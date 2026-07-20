"""Integration tests for /api/v1/wellbeing/*."""

from fastapi.testclient import TestClient


def test_formula_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/wellbeing/formula")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["formula_id"] == "wellbeing_v1"
    assert body["data"]["happiness_neq_100_minus_stress"] is True
    assert "RECOMMEND" in body["data"]["forbidden_autonomy"]


def test_current_cold_start(client: TestClient) -> None:
    response = client.get("/api/v1/wellbeing/current")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    snap = body["data"]["snapshot"]
    assert snap["data_sufficiency"] == "COLD_START"
    assert snap["happiness"] is None
    assert snap["formula_version"] == "1.0"
    assert any(a.get("capability_class") != "RECOMMEND" for a in snap["suggested_actions"])


def test_history_and_feedback(client: TestClient) -> None:
    current = client.get("/api/v1/wellbeing/current")
    score_id = current.json()["data"]["snapshot"]["score_snapshot_id"]

    hist = client.get("/api/v1/wellbeing/history")
    assert hist.status_code == 200
    assert len(hist.json()["data"]["items"]) >= 1

    expl = client.get("/api/v1/wellbeing/explanation", params={"score_snapshot_id": score_id})
    assert expl.status_code == 200
    assert expl.json()["data"]["snapshot"]["score_snapshot_id"] == score_id

    fb = client.post(
        "/api/v1/wellbeing/feedback",
        json={"score_snapshot_id": score_id, "rating": "useful", "note": "ok"},
    )
    assert fb.status_code == 200
    assert fb.json()["data"]["accepted"] is True
