"""Helpers to bootstrap a test tenant / application / credential.

Used by integration and contract tests so they can call authenticated
endpoints without going through the CLI process.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from intelligence_maxxxing import API_VERSION
from intelligence_maxxxing.application.use_cases.identity_admin import IdentityAdminService
from intelligence_maxxxing.infrastructure.health import (
    MeasuredHealthSnapshotProvider,
    SqlAlchemyDatabaseHealth,
)
from intelligence_maxxxing.infrastructure.repositories import SqlAlchemyUnitOfWork
from intelligence_maxxxing.permissions import PermissionScope


@dataclass(frozen=True)
class BootstrappedIdentity:
    tenant_id: str
    owner_id: str
    application_id: str
    credential_id: str
    secret: str

    @property
    def auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.secret}"}


DEFAULT_SCOPES = (
    PermissionScope.SUBMIT_OBSERVATION,
    PermissionScope.READ_AUDIT,
    PermissionScope.READ_INTELLIGENCE,
)


def bootstrap_test_identity(
    app: FastAPI,
    *,
    display_name: str = "test-app",
    scopes: tuple[PermissionScope, ...] = DEFAULT_SCOPES,
) -> BootstrappedIdentity:
    """Create tenant + owner + application + credential with the given scopes."""
    session_factory: sessionmaker[Session] = app.state.session_factory
    settings = app.state.settings
    health = MeasuredHealthSnapshotProvider(
        SqlAlchemyDatabaseHealth(app.state.db_engine),
        check_manifest=False,
    )
    admin = IdentityAdminService(
        uow=SqlAlchemyUnitOfWork(session_factory),
        engine_version=settings.engine_version,
        api_version=API_VERSION,
        health_provider=health,
    )

    # Reuse an existing owner if one was already bootstrapped in this DB.
    from intelligence_maxxxing.infrastructure.repositories.identity import (
        SqlAlchemyIdentityStore,
    )

    with session_factory() as session:
        identity = SqlAlchemyIdentityStore(session)
        users = list(identity.list_users())
        session.commit()

    if users:
        owner_id = users[0].id
        tenant_id = users[0].tenant_id
    else:
        tenant, user = admin.bootstrap_owner("Test Tenant", "Test Owner")
        owner_id = user.id
        tenant_id = tenant.id

    application = admin.register_application(display_name, owner_id)
    for scope in scopes:
        admin.grant_scope(application.id, scope)
    credential, secret = admin.create_credential(application.id)
    return BootstrappedIdentity(
        tenant_id=tenant_id,
        owner_id=owner_id,
        application_id=application.id,
        credential_id=credential.credential_id,
        secret=secret,
    )


def _make_admin(app: FastAPI) -> IdentityAdminService:
    session_factory: sessionmaker[Session] = app.state.session_factory
    settings = app.state.settings
    health = MeasuredHealthSnapshotProvider(
        SqlAlchemyDatabaseHealth(app.state.db_engine),
        check_manifest=False,
    )
    return IdentityAdminService(
        uow=SqlAlchemyUnitOfWork(session_factory),
        engine_version=settings.engine_version,
        api_version=API_VERSION,
        health_provider=health,
    )


def register_application_for(
    app: FastAPI,
    *,
    owner_id: str,
    display_name: str,
    scopes: tuple[PermissionScope, ...] = DEFAULT_SCOPES,
) -> BootstrappedIdentity:
    """Register an additional application under an EXISTING owner.

    Used for same-owner cross-application isolation tests (App A vs App B).
    """
    admin = _make_admin(app)
    application = admin.register_application(display_name, owner_id)
    for scope in scopes:
        admin.grant_scope(application.id, scope)
    credential, secret = admin.create_credential(application.id)
    return BootstrappedIdentity(
        tenant_id=application.tenant_id,
        owner_id=owner_id,
        application_id=application.id,
        credential_id=credential.credential_id,
        secret=secret,
    )


def bootstrap_isolated_identity(
    app: FastAPI,
    *,
    tenant_name: str,
    owner_name: str,
    display_name: str,
    scopes: tuple[PermissionScope, ...] = DEFAULT_SCOPES,
) -> BootstrappedIdentity:
    """Create a brand-new tenant + owner + application (fully isolated).

    Unlike bootstrap_test_identity, this never reuses the existing owner, so it
    can be used for cross-tenant isolation tests.
    """
    from intelligence_maxxxing.domain.common.base import utc_now
    from intelligence_maxxxing.domain.common.identifiers import (
        TENANT_PREFIX,
        USER_PREFIX,
        new_id,
    )
    from intelligence_maxxxing.domain.identity import TenantIdentity, UserIdentity
    from intelligence_maxxxing.infrastructure.repositories.identity import (
        SqlAlchemyIdentityStore,
    )

    session_factory: sessionmaker[Session] = app.state.session_factory
    with session_factory() as session:
        store = SqlAlchemyIdentityStore(session)
        tenant = TenantIdentity(
            id=new_id(TENANT_PREFIX),
            display_name=tenant_name,
            created_at=utc_now(),
            audit_id="aud_" + "e" * 32,
        )
        owner = UserIdentity(
            id=new_id(USER_PREFIX),
            tenant_id=tenant.id,
            display_name=owner_name,
            created_at=utc_now(),
            audit_id="aud_" + "e" * 32,
        )
        store.add_tenant(tenant)
        store.add_user(owner)
        session.commit()

    return register_application_for(
        app, owner_id=owner.id, display_name=display_name, scopes=scopes
    )
