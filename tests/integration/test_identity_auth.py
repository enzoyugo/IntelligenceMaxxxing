"""Identity and authentication tests.

ACTOR_COMES_FROM_AUTH_CONTEXT / BODY_CANNOT_SPOOF_ACTOR /
DISABLED_APPLICATION_REJECTED / REVOKED_CREDENTIAL_REJECTED /
EXPIRED_CREDENTIAL_REJECTED / INVALID_CREDENTIAL_REJECTED
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from intelligence_maxxxing.domain.identity import CredentialStatus, IdentityStatus
from intelligence_maxxxing.infrastructure.repositories.identity import SqlAlchemyIdentityStore
from tests.conftest import valid_observation_payload
from tests.fixtures.identity import bootstrap_test_identity


def test_actor_comes_from_auth_context(app: FastAPI, client: TestClient, identity: object) -> None:
    response = client.post(
        "/api/v1/observations",
        json=valid_observation_payload(),
        headers={"Idempotency-Key": f"actor-{uuid.uuid4().hex}"},
    )
    assert response.status_code == 201
    audit_id = response.json()["data"]["audit_id"]
    audit = client.get(f"/api/v1/audits/{audit_id}").json()["data"]
    assert audit["actor_type"] == "APPLICATION"
    assert audit["actor_id"] == identity.application_id  # type: ignore[attr-defined]


def test_body_cannot_spoof_actor(app: FastAPI, client: TestClient, identity: object) -> None:
    payload = valid_observation_payload()
    payload["observed_by"] = "spoofed-other-app"
    # Extra actor fields are rejected by the public schema.
    payload_with_actor = dict(payload)
    payload_with_actor["actor_id"] = "app_attacker"
    rejected = client.post(
        "/api/v1/observations",
        json=payload_with_actor,
        headers={"Idempotency-Key": f"spoof-{uuid.uuid4().hex}"},
    )
    assert rejected.status_code == 422

    accepted = client.post(
        "/api/v1/observations",
        json=payload,
        headers={"Idempotency-Key": f"spoof2-{uuid.uuid4().hex}"},
    )
    assert accepted.status_code == 201
    audit = client.get(f"/api/v1/audits/{accepted.json()['data']['audit_id']}").json()["data"]
    assert audit["actor_id"] == identity.application_id  # type: ignore[attr-defined]
    assert audit["actor_id"] != "spoofed-other-app"


def test_invalid_credential_rejected(app: FastAPI) -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/api/v1/health",
            headers={"Authorization": "Bearer imx_sk_deadbeefdeadbeefdeadbeefXXXXXXXX"},
        )
    assert response.status_code == 401


def test_revoked_credential_rejected(app: FastAPI) -> None:
    identity = bootstrap_test_identity(app, display_name="revocable")
    with app.state.session_factory() as session:
        store = SqlAlchemyIdentityStore(session)
        store.set_credential_status(
            identity.credential_id, CredentialStatus.REVOKED, datetime.now(UTC)
        )
        session.commit()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/health", headers=identity.auth_header)
    assert response.status_code == 401
    assert "revoked" in response.json()["error"]["message"]


def test_expired_credential_rejected(app: FastAPI) -> None:
    from intelligence_maxxxing.infrastructure.database.tables import ApplicationCredentialRow

    identity = bootstrap_test_identity(app, display_name="expiring")
    past = datetime.now(UTC) - timedelta(hours=1)
    with app.state.session_factory() as session:
        row = session.get(ApplicationCredentialRow, identity.credential_id)
        assert row is not None
        row.expires_at = past
        session.commit()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/health", headers=identity.auth_header)
    assert response.status_code == 401
    assert "expired" in response.json()["error"]["message"]


def test_disabled_application_rejected(app: FastAPI) -> None:
    identity = bootstrap_test_identity(app, display_name="disable-me")
    with app.state.session_factory() as session:
        store = SqlAlchemyIdentityStore(session)
        store.set_application_status(
            identity.application_id, IdentityStatus.DISABLED, datetime.now(UTC)
        )
        session.commit()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/health", headers=identity.auth_header)
    assert response.status_code == 401
    assert "disabled" in response.json()["error"]["message"]
