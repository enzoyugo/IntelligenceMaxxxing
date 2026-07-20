"""Integration smoke test: propose → activate → evaluate (insufficient evidence)."""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from intelligence_maxxxing.domain.common.epistemic import BeliefState, EvidencePhase
from intelligence_maxxxing.permissions import PermissionScope
from tests.fixtures.identity import DEFAULT_SCOPES, bootstrap_test_identity

EPISTEMIC_SCOPES = (
    *DEFAULT_SCOPES,
    PermissionScope.SUBMIT_HYPOTHESIS,
    PermissionScope.READ_HYPOTHESIS,
    PermissionScope.MANAGE_EXPERIMENT,
    PermissionScope.READ_BELIEF,
    PermissionScope.READ_LEARNING,
)


@pytest.fixture()
def epistemic_client(app: FastAPI) -> TestClient:
    identity = bootstrap_test_identity(app, scopes=EPISTEMIC_SCOPES)
    with TestClient(app, raise_server_exceptions=False) as client:
        client.headers.update(identity.auth_header)
        yield client


def _idem() -> str:
    return f"key-{uuid.uuid4().hex}"


def _default_parameters() -> dict[str, object]:
    return {
        "sleep_threshold_hours": 7.0,
        "minimum_meaningful_difference": 0.5,
        "prospective_target": 14,
        "maximum_window_days": 42,
    }


class TestEpistemicSmokePath:
    def test_propose_activate_evaluate_insufficient(self, epistemic_client: TestClient) -> None:
        client = epistemic_client

        proposed = client.post(
            "/api/v1/hypotheses",
            json={"human_confirmed": False},
            headers={"Idempotency-Key": _idem()},
        )
        assert proposed.status_code == 201, proposed.text
        hypothesis_id = proposed.json()["data"]["hypothesis_id"]
        assert hypothesis_id.startswith("hyp_")

        activated = client.post(
            f"/api/v1/hypotheses/{hypothesis_id}/activate",
            json={"parameters": _default_parameters()},
            headers={"Idempotency-Key": _idem()},
        )
        assert activated.status_code == 201, activated.text
        experiment_id = activated.json()["data"]["experiment_id"]
        assert experiment_id.startswith("exp_")

        evaluated = client.post(
            f"/api/v1/experiments/{experiment_id}/evaluate",
            json={"phase": EvidencePhase.BASELINE_EXPLORATORY.value},
            headers={"Idempotency-Key": _idem()},
        )
        assert evaluated.status_code == 201, evaluated.text
        body = evaluated.json()
        assert body["ok"] is True
        assert body["data"]["belief_state"] == BeliefState.INSUFFICIENT_EVIDENCE.value
        assert body["data"]["evidence_id"].startswith("evd_")
        assert body["data"]["belief_id"].startswith("blf_")

        hypothesis = client.get(f"/api/v1/hypotheses/{hypothesis_id}")
        assert hypothesis.status_code == 200
        assert hypothesis.json()["data"]["status"] == "OBSERVING"

        progress = client.get(f"/api/v1/experiments/{experiment_id}/progress")
        assert progress.status_code == 200
        assert progress.json()["data"]["current_belief_state"] == (
            BeliefState.INSUFFICIENT_EVIDENCE.value
        )

        belief = client.get(f"/api/v1/hypotheses/{hypothesis_id}/beliefs/current")
        assert belief.status_code == 200
        belief_data = belief.json()["data"]
        assert belief_data is not None
        assert belief_data["belief_state"] == BeliefState.INSUFFICIENT_EVIDENCE.value
        assert belief_data["recommendation_confidence"] == "VERY_LOW"
        assert belief_data["calibration_state"] == "UNCALIBRATED"
        assert belief_data["causality_level"] == "CORRELATION"
        assert any("observational" in lim.lower() for lim in belief_data["limitations"])

    def test_propose_idempotent_retry(self, epistemic_client: TestClient) -> None:
        client = epistemic_client
        key = _idem()
        first = client.post(
            "/api/v1/hypotheses",
            json={"human_confirmed": False},
            headers={"Idempotency-Key": key},
        )
        retry = client.post(
            "/api/v1/hypotheses",
            json={"human_confirmed": False},
            headers={"Idempotency-Key": key},
        )
        assert first.status_code == 201
        assert retry.status_code == 200
        assert retry.json()["data"]["replayed"] is True
        assert retry.json()["data"]["hypothesis_id"] == first.json()["data"]["hypothesis_id"]
