"""Application-scoped audit isolation (Stage 1.1 §3, §10).

APPLICATION_CANNOT_READ_OTHER_APPLICATION_AUDIT_SAME_OWNER
APPLICATION_CANNOT_READ_OTHER_APPLICATION_EVENTS_SAME_OWNER
APPLICATION_CAN_READ_OWN_AUDIT
CROSS_TENANT_AUDIT_ACCESS_REJECTED
AUDIT_SCOPE_REQUIRES_TENANT_OWNER_APPLICATION

The confirmed exploit: two applications of the SAME owner must not read each
other's audits. App B requesting App A's audit gets 404 (not 403), so its very
existence is not leaked.
"""

import inspect
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from intelligence_maxxxing.application.ports import AuditStorePort, EventStorePort
from tests.conftest import valid_observation_payload
from tests.fixtures.identity import (
    bootstrap_isolated_identity,
    bootstrap_test_identity,
    register_application_for,
)


def _submit(client: TestClient, secret: str) -> str:
    response = client.post(
        "/api/v1/observations",
        json=valid_observation_payload(),
        headers={
            "Authorization": f"Bearer {secret}",
            "Idempotency-Key": f"iso-{uuid.uuid4().hex}",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["audit_id"]


def test_application_cannot_read_other_application_audit_same_owner(app: FastAPI) -> None:
    """The exact confirmed exploit: App B (same owner) reading App A's audit -> 404."""
    app_a = bootstrap_test_identity(app, display_name="LifeMaxxxing")
    app_b = register_application_for(app, owner_id=app_a.owner_id, display_name="TradingMaxxxing")
    assert app_a.owner_id == app_b.owner_id
    assert app_a.application_id != app_b.application_id

    with TestClient(app, raise_server_exceptions=False) as client:
        audit_a = _submit(client, app_a.secret)
        response = client.get(
            f"/api/v1/audits/{audit_a}",
            headers={"Authorization": f"Bearer {app_b.secret}"},
        )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AUDIT_NOT_FOUND"


def test_application_cannot_read_other_application_events_same_owner(app: FastAPI) -> None:
    app_a = bootstrap_test_identity(app, display_name="app-a-events")
    app_b = register_application_for(app, owner_id=app_a.owner_id, display_name="app-b-events")
    with TestClient(app, raise_server_exceptions=False) as client:
        audit_a = _submit(client, app_a.secret)
        # 404 hides both the audit AND its events from App B.
        response = client.get(
            f"/api/v1/audits/{audit_a}",
            headers={"Authorization": f"Bearer {app_b.secret}"},
        )
    assert response.status_code == 404


def test_application_can_read_own_audit(app: FastAPI) -> None:
    app_a = bootstrap_test_identity(app, display_name="own-reader")
    with TestClient(app, raise_server_exceptions=False) as client:
        audit_a = _submit(client, app_a.secret)
        response = client.get(
            f"/api/v1/audits/{audit_a}",
            headers={"Authorization": f"Bearer {app_a.secret}"},
        )
    assert response.status_code == 200
    assert response.json()["data"]["audit_id"] == audit_a


def test_cross_tenant_audit_access_rejected(app: FastAPI) -> None:
    app_a = bootstrap_test_identity(app, display_name="tenant-a-app")
    other = bootstrap_isolated_identity(
        app,
        tenant_name="Other Tenant",
        owner_name="Other Owner",
        display_name="tenant-b-app",
    )
    assert app_a.tenant_id != other.tenant_id
    with TestClient(app, raise_server_exceptions=False) as client:
        audit_a = _submit(client, app_a.secret)
        response = client.get(
            f"/api/v1/audits/{audit_a}",
            headers={"Authorization": f"Bearer {other.secret}"},
        )
    assert response.status_code == 404


def test_audit_scope_requires_tenant_owner_application() -> None:
    """The store contract itself is scoped by tenant + owner + application."""
    audit_params = set(inspect.signature(AuditStorePort.get_by_audit_id).parameters)
    assert {"tenant_id", "owner_id", "application_id", "audit_id"} <= audit_params

    events_params = set(inspect.signature(EventStorePort.list_by_audit).parameters)
    assert {"tenant_id", "owner_id", "application_id", "audit_id"} <= events_params
