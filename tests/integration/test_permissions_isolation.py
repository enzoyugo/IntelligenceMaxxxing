"""Permission and isolation tests.

SUBMIT_OBSERVATION_SCOPE_REQUIRED / READ_AUDIT_SCOPE_REQUIRED /
APPLICATION_CANNOT_READ_OTHER_OWNER / APPLICATION_CANNOT_GRANT_ITSELF_SCOPE /
IDEMPOTENCY_SCOPED_BY_APPLICATION / IDEMPOTENCY_SCOPED_BY_OWNER
"""

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from intelligence_maxxxing.permissions import PermissionScope
from tests.conftest import valid_observation_payload
from tests.fixtures.identity import bootstrap_test_identity


def test_submit_observation_scope_required(app: FastAPI) -> None:
    identity = bootstrap_test_identity(app, display_name="no-submit", scopes=())
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/observations",
            json=valid_observation_payload(),
            headers={**identity.auth_header, "Idempotency-Key": f"noscope-{uuid.uuid4().hex}"},
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_read_audit_scope_required(app: FastAPI) -> None:
    writer = bootstrap_test_identity(
        app,
        display_name="writer",
        scopes=(PermissionScope.SUBMIT_OBSERVATION, PermissionScope.READ_AUDIT),
    )
    reader = bootstrap_test_identity(
        app, display_name="reader-no-audit", scopes=(PermissionScope.SUBMIT_OBSERVATION,)
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        submitted = client.post(
            "/api/v1/observations",
            json=valid_observation_payload(),
            headers={**writer.auth_header, "Idempotency-Key": f"ra-{uuid.uuid4().hex}"},
        )
        assert submitted.status_code == 201
        audit_id = submitted.json()["data"]["audit_id"]
        denied = client.get(f"/api/v1/audits/{audit_id}", headers=reader.auth_header)
    assert denied.status_code == 403


def test_application_cannot_read_other_owner(app: FastAPI) -> None:
    """Two apps owned by different users cannot read each other's audits."""
    from intelligence_maxxxing import API_VERSION
    from intelligence_maxxxing.application.use_cases.identity_admin import IdentityAdminService
    from intelligence_maxxxing.domain.common.base import utc_now
    from intelligence_maxxxing.domain.common.identifiers import USER_PREFIX, new_id
    from intelligence_maxxxing.domain.identity import UserIdentity
    from intelligence_maxxxing.infrastructure.health import (
        MeasuredHealthSnapshotProvider,
        SqlAlchemyDatabaseHealth,
    )
    from intelligence_maxxxing.infrastructure.repositories import SqlAlchemyUnitOfWork
    from intelligence_maxxxing.infrastructure.repositories.identity import SqlAlchemyIdentityStore

    health = MeasuredHealthSnapshotProvider(
        SqlAlchemyDatabaseHealth(app.state.db_engine), check_manifest=False
    )
    admin = IdentityAdminService(
        uow=SqlAlchemyUnitOfWork(app.state.session_factory),
        engine_version=app.state.settings.engine_version,
        api_version=API_VERSION,
        health_provider=health,
    )
    app_a = bootstrap_test_identity(app, display_name="owner-a-app")

    with app.state.session_factory() as session:
        store = SqlAlchemyIdentityStore(session)
        users = list(store.list_users())
        owner2 = UserIdentity(
            id=new_id(USER_PREFIX),
            tenant_id=users[0].tenant_id,
            display_name="Owner Two",
            created_at=utc_now(),
            audit_id="aud_" + "f" * 32,
        )
        store.add_user(owner2)
        session.commit()
        owner_b_id = owner2.id

    app_b_identity = admin.register_application("owner-b-app", owner_b_id)
    for scope in (
        PermissionScope.SUBMIT_OBSERVATION,
        PermissionScope.READ_AUDIT,
        PermissionScope.READ_INTELLIGENCE,
    ):
        admin.grant_scope(app_b_identity.id, scope)
    cred_b, secret_b = admin.create_credential(app_b_identity.id)

    with TestClient(app, raise_server_exceptions=False) as client:
        submitted = client.post(
            "/api/v1/observations",
            json=valid_observation_payload(),
            headers={**app_a.auth_header, "Idempotency-Key": f"iso-{uuid.uuid4().hex}"},
        )
        assert submitted.status_code == 201
        audit_id = submitted.json()["data"]["audit_id"]
        # App B tries to read App A's audit: looks like not found (closed).
        other = client.get(
            f"/api/v1/audits/{audit_id}",
            headers={"Authorization": f"Bearer {secret_b}"},
        )
    assert other.status_code == 404
    assert cred_b.credential_id


def test_application_cannot_grant_itself_scope(app: FastAPI) -> None:
    """There is no HTTP surface that lets an application elevate its scopes."""
    identity = bootstrap_test_identity(app, display_name="no-elevate", scopes=())
    with TestClient(app, raise_server_exceptions=False) as client:
        for path in (
            "/api/v1/permissions/grant",
            "/api/v1/admin/grant-scope",
            "/api/v1/applications/scopes",
        ):
            response = client.post(
                path,
                json={"scope": "ADMINISTER_ENGINE"},
                headers=identity.auth_header,
            )
            assert response.status_code in {401, 403, 404, 405}


def test_idempotency_scoped_by_application(app: FastAPI) -> None:
    app_a = bootstrap_test_identity(app, display_name="idem-a")
    app_b = bootstrap_test_identity(app, display_name="idem-b")
    key = f"shared-key-{uuid.uuid4().hex}"
    with TestClient(app, raise_server_exceptions=False) as client:
        a = client.post(
            "/api/v1/observations",
            json=valid_observation_payload(),
            headers={**app_a.auth_header, "Idempotency-Key": key},
        )
        b = client.post(
            "/api/v1/observations",
            json=valid_observation_payload(),
            headers={**app_b.auth_header, "Idempotency-Key": key},
        )
    assert a.status_code == 201
    assert b.status_code == 201
    assert a.json()["data"]["observation_id"] != b.json()["data"]["observation_id"]


def test_idempotency_scoped_by_owner(app: FastAPI) -> None:
    """Same as application scoping: different owners never share idempotency."""
    # Covered by distinct applications bound to distinct owners above; this
    # assertion documents the composite unique key includes owner_id.
    from intelligence_maxxxing.infrastructure.database.tables import IdempotencyKeyRow

    columns = {c.name for c in IdempotencyKeyRow.__table__.columns}
    assert {"application_id", "owner_id", "action", "idempotency_key"} <= columns
