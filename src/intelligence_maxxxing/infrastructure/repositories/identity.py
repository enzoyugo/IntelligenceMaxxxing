"""SQLAlchemy identity registry (tenants, users, applications, credentials)."""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from intelligence_maxxxing.application.ports import CredentialRecord, IdentityStorePort
from intelligence_maxxxing.domain.identity import (
    ApplicationIdentity,
    CredentialStatus,
    IdentityStatus,
    TenantIdentity,
    UserIdentity,
)
from intelligence_maxxxing.infrastructure.database.tables import (
    ApplicationCredentialRow,
    ApplicationRow,
    TenantRow,
    UserRow,
)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _as_utc_opt(value: datetime | None) -> datetime | None:
    return None if value is None else _as_utc(value)


class SqlAlchemyIdentityStore(IdentityStorePort):
    def __init__(self, session: Session) -> None:
        self._session = session

    # ---------------------------------------------------------------- tenants

    def add_tenant(self, tenant: TenantIdentity) -> None:
        self._session.add(
            TenantRow(
                id=tenant.id,
                schema_version=tenant.schema_version,
                status=tenant.status.value,
                display_name=tenant.display_name,
                created_at=tenant.created_at,
                disabled_at=tenant.disabled_at,
                meta=dict(tenant.metadata),
                audit_id=tenant.audit_id,
            )
        )

    def get_tenant(self, tenant_id: str) -> TenantIdentity | None:
        row = self._session.get(TenantRow, tenant_id)
        return None if row is None else _tenant(row)

    def list_tenants(self) -> Sequence[TenantIdentity]:
        return [_tenant(r) for r in self._session.scalars(select(TenantRow))]

    # ------------------------------------------------------------------ users

    def add_user(self, user: UserIdentity) -> None:
        self._session.add(
            UserRow(
                id=user.id,
                schema_version=user.schema_version,
                tenant_id=user.tenant_id,
                status=user.status.value,
                display_name=user.display_name,
                created_at=user.created_at,
                disabled_at=user.disabled_at,
                meta=dict(user.metadata),
                audit_id=user.audit_id,
            )
        )

    def get_user(self, user_id: str) -> UserIdentity | None:
        row = self._session.get(UserRow, user_id)
        return None if row is None else _user(row)

    def list_users(self) -> Sequence[UserIdentity]:
        return [_user(r) for r in self._session.scalars(select(UserRow))]

    # ----------------------------------------------------------- applications

    def add_application(self, application: ApplicationIdentity, scopes: Sequence[str]) -> None:
        self._session.add(
            ApplicationRow(
                id=application.id,
                schema_version=application.schema_version,
                tenant_id=application.tenant_id,
                owner_id=application.owner_id,
                status=application.status.value,
                display_name=application.display_name,
                scopes=list(scopes),
                created_at=application.created_at,
                disabled_at=application.disabled_at,
                meta=dict(application.metadata),
                audit_id=application.audit_id,
            )
        )

    def get_application(self, application_id: str) -> ApplicationIdentity | None:
        row = self._session.get(ApplicationRow, application_id)
        return None if row is None else _application(row)

    def list_applications(self) -> Sequence[ApplicationIdentity]:
        return [_application(r) for r in self._session.scalars(select(ApplicationRow))]

    def get_application_scopes(self, application_id: str) -> Sequence[str]:
        row = self._session.get(ApplicationRow, application_id)
        return [] if row is None else list(row.scopes)

    def set_application_scopes(self, application_id: str, scopes: Sequence[str]) -> None:
        row = self._session.get(ApplicationRow, application_id)
        if row is None:
            raise LookupError(application_id)
        row.scopes = list(scopes)

    def set_application_status(
        self, application_id: str, status: IdentityStatus, disabled_at: datetime | None
    ) -> None:
        row = self._session.get(ApplicationRow, application_id)
        if row is None:
            raise LookupError(application_id)
        row.status = status.value
        row.disabled_at = disabled_at

    # ----------------------------------------------------------- credentials

    def add_credential(self, credential: CredentialRecord) -> None:
        self._session.add(
            ApplicationCredentialRow(
                credential_id=credential.credential_id,
                application_id=credential.application_id,
                secret_hash=credential.secret_hash,
                status=credential.status.value,
                created_at=credential.created_at,
                expires_at=credential.expires_at,
                revoked_at=credential.revoked_at,
                last_used_at=credential.last_used_at,
                audit_id=credential.audit_id,
            )
        )

    def get_credential(self, credential_id: str) -> CredentialRecord | None:
        row = self._session.get(ApplicationCredentialRow, credential_id)
        return None if row is None else _credential(row)

    def list_credentials(self, application_id: str) -> Sequence[CredentialRecord]:
        stmt = select(ApplicationCredentialRow).where(
            ApplicationCredentialRow.application_id == application_id
        )
        return [_credential(r) for r in self._session.scalars(stmt)]

    def set_credential_status(
        self, credential_id: str, status: CredentialStatus, revoked_at: datetime | None
    ) -> None:
        row = self._session.get(ApplicationCredentialRow, credential_id)
        if row is None:
            raise LookupError(credential_id)
        row.status = status.value
        row.revoked_at = revoked_at

    def touch_credential(self, credential_id: str, last_used_at: datetime) -> None:
        row = self._session.get(ApplicationCredentialRow, credential_id)
        if row is None:
            raise LookupError(credential_id)
        row.last_used_at = last_used_at


def _tenant(row: TenantRow) -> TenantIdentity:
    return TenantIdentity(
        id=row.id,
        schema_version=row.schema_version,
        status=IdentityStatus(row.status),
        display_name=row.display_name,
        created_at=_as_utc(row.created_at),
        disabled_at=_as_utc_opt(row.disabled_at),
        metadata=dict(row.meta),  # type: ignore[arg-type]
        audit_id=row.audit_id,
    )


def _user(row: UserRow) -> UserIdentity:
    return UserIdentity(
        id=row.id,
        schema_version=row.schema_version,
        tenant_id=row.tenant_id,
        status=IdentityStatus(row.status),
        display_name=row.display_name,
        created_at=_as_utc(row.created_at),
        disabled_at=_as_utc_opt(row.disabled_at),
        metadata=dict(row.meta),  # type: ignore[arg-type]
        audit_id=row.audit_id,
    )


def _application(row: ApplicationRow) -> ApplicationIdentity:
    return ApplicationIdentity(
        id=row.id,
        schema_version=row.schema_version,
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        status=IdentityStatus(row.status),
        display_name=row.display_name,
        created_at=_as_utc(row.created_at),
        disabled_at=_as_utc_opt(row.disabled_at),
        metadata=dict(row.meta),  # type: ignore[arg-type]
        audit_id=row.audit_id,
    )


def _credential(row: ApplicationCredentialRow) -> CredentialRecord:
    return CredentialRecord(
        credential_id=row.credential_id,
        application_id=row.application_id,
        secret_hash=row.secret_hash,
        status=CredentialStatus(row.status),
        created_at=_as_utc(row.created_at),
        expires_at=_as_utc_opt(row.expires_at),
        revoked_at=_as_utc_opt(row.revoked_at),
        last_used_at=_as_utc_opt(row.last_used_at),
        audit_id=row.audit_id,
    )
