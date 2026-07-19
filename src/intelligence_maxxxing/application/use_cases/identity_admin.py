"""Governed identity administration (Stage 1 §5, §6, §17).

These use cases are invoked ONLY by the local CLI (never by public HTTP
endpoints). Every action appends catalog events and an audit record with a
measured health snapshot.
"""

import secrets
from collections.abc import Sequence
from datetime import datetime

from intelligence_maxxxing.application.auth.service import (
    generate_credential_secret,
    hash_credential_secret,
)
from intelligence_maxxxing.application.errors import IdentityError
from intelligence_maxxxing.application.ports import (
    CredentialRecord,
    HealthSnapshotProviderPort,
    UnitOfWorkPort,
)
from intelligence_maxxxing.domain.audit.models import Actor, AuditRecord, EngineEvent
from intelligence_maxxxing.domain.common.base import CANONICAL_SCHEMA_VERSION, utc_now
from intelligence_maxxxing.domain.common.epistemic import ActorType
from intelligence_maxxxing.domain.common.identifiers import (
    APPLICATION_PREFIX,
    AUDIT_PREFIX,
    EVENT_PREFIX,
    TENANT_PREFIX,
    USER_PREFIX,
    new_id,
)
from intelligence_maxxxing.domain.identity import (
    ApplicationIdentity,
    CredentialStatus,
    IdentityStatus,
    TenantIdentity,
    UserIdentity,
)
from intelligence_maxxxing.domain.identity.system import SYSTEM_APPLICATION_ID
from intelligence_maxxxing.permissions import PermissionScope


class IdentityAdminService:
    """Local, governed identity administration."""

    def __init__(
        self,
        uow: UnitOfWorkPort,
        engine_version: str,
        api_version: str,
        health_provider: HealthSnapshotProviderPort,
        admin_actor_id: str = "constitutional-owner",
    ) -> None:
        self._uow = uow
        self._engine_version = engine_version
        self._api_version = api_version
        self._health = health_provider
        self._actor = Actor(actor_type=ActorType.HUMAN, actor_id=admin_actor_id)

    # ------------------------------------------------------------------ utils

    def _next_version(self, uow: UnitOfWorkPort, aggregate_type: str, aggregate_id: str) -> int:
        latest = uow.events.get_latest_aggregate_version(aggregate_type, aggregate_id)
        return (latest or 0) + 1

    def _audit(
        self,
        uow: UnitOfWorkPort,
        *,
        audit_id: str,
        action: str,
        tenant_id: str,
        owner_id: str,
        input_ids: Sequence[str],
        output_ids: Sequence[str],
        event_ids: Sequence[str],
        occurred_at: datetime,
    ) -> None:
        snapshot = self._health.capture()
        uow.audits.append(
            AuditRecord(
                audit_id=audit_id,
                request_id=f"cli_{secrets.token_hex(8)}",
                engine_version=self._engine_version,
                api_version=self._api_version,
                schema_version=CANONICAL_SCHEMA_VERSION,
                domain_pack="core",
                tenant_id=tenant_id,
                owner_id=owner_id,
                application_id=SYSTEM_APPLICATION_ID,
                actor=self._actor,
                action=action,
                input_object_ids=tuple(input_ids),
                output_object_ids=tuple(output_ids),
                event_ids=tuple(event_ids),
                timestamp=occurred_at,
                health_state=snapshot.model_dump(mode="json"),
            )
        )

    def _event(
        self,
        uow: UnitOfWorkPort,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        tenant_id: str,
        owner_id: str,
        payload: dict[str, object],
        audit_id: str,
        occurred_at: datetime,
    ) -> EngineEvent:
        event = EngineEvent(
            event_id=new_id(EVENT_PREFIX),
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            aggregate_version=self._next_version(uow, aggregate_type, aggregate_id),
            domain_pack="core",
            tenant_id=tenant_id,
            owner_id=owner_id,
            application_id=SYSTEM_APPLICATION_ID,
            actor=self._actor,
            schema_version=CANONICAL_SCHEMA_VERSION,
            payload=payload,
            occurred_at=occurred_at,
            recorded_at=occurred_at,
            audit_id=audit_id,
            request_id=audit_id,
        )
        return uow.events.append_one(event)

    # ------------------------------------------------------------- bootstrap

    def bootstrap_owner(
        self, tenant_display_name: str, owner_display_name: str
    ) -> tuple[TenantIdentity, UserIdentity]:
        """Create the private tenant and the Constitutional Owner user."""
        with self._uow as uow:
            if uow.identity.list_users():
                raise IdentityError("owner is already bootstrapped")
            now = utc_now()
            audit_id = new_id(AUDIT_PREFIX)
            tenant = TenantIdentity(
                id=new_id(TENANT_PREFIX),
                display_name=tenant_display_name,
                created_at=now,
                audit_id=audit_id,
            )
            user = UserIdentity(
                id=new_id(USER_PREFIX),
                tenant_id=tenant.id,
                display_name=owner_display_name,
                created_at=now,
                audit_id=audit_id,
            )
            uow.identity.add_tenant(tenant)
            uow.identity.add_user(user)
            event = self._event(
                uow,
                event_type="UserRegistered",
                aggregate_type="User",
                aggregate_id=user.id,
                tenant_id=tenant.id,
                owner_id=user.id,
                payload={
                    "user_id": user.id,
                    "tenant_id": tenant.id,
                    "display_name": user.display_name,
                    "registered_at": now.isoformat(),
                },
                audit_id=audit_id,
                occurred_at=now,
            )
            self._audit(
                uow,
                audit_id=audit_id,
                action="identity.bootstrap_owner",
                tenant_id=tenant.id,
                owner_id=user.id,
                input_ids=(),
                output_ids=(tenant.id, user.id),
                event_ids=(event.event_id,),
                occurred_at=now,
            )
            uow.commit()
        return tenant, user

    # ----------------------------------------------------------- applications

    def register_application(self, display_name: str, owner_id: str) -> ApplicationIdentity:
        """Register an application bound to an existing owner.

        The owner is assigned HERE, by the administrator; an application can
        never choose its own owner_id at request time.
        """
        with self._uow as uow:
            owner = uow.identity.get_user(owner_id)
            if owner is None:
                raise IdentityError(f"owner {owner_id!r} does not exist")
            now = utc_now()
            audit_id = new_id(AUDIT_PREFIX)
            application = ApplicationIdentity(
                id=new_id(APPLICATION_PREFIX),
                tenant_id=owner.tenant_id,
                owner_id=owner.id,
                display_name=display_name,
                created_at=now,
                audit_id=audit_id,
            )
            uow.identity.add_application(application, scopes=())
            event = self._event(
                uow,
                event_type="ApplicationRegistered",
                aggregate_type="Application",
                aggregate_id=application.id,
                tenant_id=application.tenant_id,
                owner_id=application.owner_id,
                payload={
                    "application_id": application.id,
                    "display_name": application.display_name,
                    "tenant_id": application.tenant_id,
                    "owner_id": application.owner_id,
                    "schema_version": application.schema_version,
                    "registered_at": now.isoformat(),
                },
                audit_id=audit_id,
                occurred_at=now,
            )
            self._audit(
                uow,
                audit_id=audit_id,
                action="identity.register_application",
                tenant_id=application.tenant_id,
                owner_id=application.owner_id,
                input_ids=(owner.id,),
                output_ids=(application.id,),
                event_ids=(event.event_id,),
                occurred_at=now,
            )
            uow.commit()
        return application

    def set_application_status(self, application_id: str, status: IdentityStatus) -> None:
        with self._uow as uow:
            application = self._require_application(uow, application_id)
            now = utc_now()
            disabled_at = now if status is IdentityStatus.DISABLED else None
            uow.identity.set_application_status(application.id, status, disabled_at)
            uow.commit()

    def list_applications(self) -> Sequence[ApplicationIdentity]:
        with self._uow as uow:
            applications = list(uow.identity.list_applications())
            uow.commit()
        return applications

    def _require_application(self, uow: UnitOfWorkPort, application_id: str) -> ApplicationIdentity:
        application = uow.identity.get_application(application_id)
        if application is None:
            raise IdentityError(f"application {application_id!r} does not exist")
        return application

    # ------------------------------------------------------------ credentials

    def create_credential(
        self, application_id: str, expires_at: datetime | None = None
    ) -> tuple[CredentialRecord, str]:
        """Create a credential. The plaintext secret is returned exactly once
        and is never stored or logged."""
        with self._uow as uow:
            application = self._require_application(uow, application_id)
            now = utc_now()
            audit_id = new_id(AUDIT_PREFIX)
            credential, plaintext = self._new_credential(application.id, audit_id, expires_at)
            uow.identity.add_credential(credential)
            event = self._event(
                uow,
                event_type="ApplicationCredentialCreated",
                aggregate_type="ApplicationCredential",
                aggregate_id=credential.credential_id,
                tenant_id=application.tenant_id,
                owner_id=application.owner_id,
                payload={
                    "credential_id": credential.credential_id,
                    "application_id": application.id,
                    "created_at": now.isoformat(),
                    "expires_at": expires_at.isoformat() if expires_at else None,
                },
                audit_id=audit_id,
                occurred_at=now,
            )
            self._audit(
                uow,
                audit_id=audit_id,
                action="identity.create_credential",
                tenant_id=application.tenant_id,
                owner_id=application.owner_id,
                input_ids=(application.id,),
                output_ids=(credential.credential_id,),
                event_ids=(event.event_id,),
                occurred_at=now,
            )
            uow.commit()
        return credential, plaintext

    def _new_credential(
        self, application_id: str, audit_id: str, expires_at: datetime | None
    ) -> tuple[CredentialRecord, str]:
        credential_hex = secrets.token_hex(12)  # 24 hex chars
        plaintext = generate_credential_secret(credential_hex)
        credential = CredentialRecord(
            credential_id=f"cred_{credential_hex}",
            application_id=application_id,
            secret_hash=hash_credential_secret(plaintext),
            status=CredentialStatus.ACTIVE,
            created_at=utc_now(),
            expires_at=expires_at,
            audit_id=audit_id,
        )
        return credential, plaintext

    def rotate_credential(self, credential_id: str) -> tuple[CredentialRecord, str]:
        """Revoke the old credential and issue a fresh one atomically."""
        with self._uow as uow:
            old = uow.identity.get_credential(credential_id)
            if old is None:
                raise IdentityError(f"credential {credential_id!r} does not exist")
            application = self._require_application(uow, old.application_id)
            now = utc_now()
            audit_id = new_id(AUDIT_PREFIX)
            uow.identity.set_credential_status(credential_id, CredentialStatus.REVOKED, now)
            new_credential, plaintext = self._new_credential(application.id, audit_id, None)
            uow.identity.add_credential(new_credential)
            event = self._event(
                uow,
                event_type="ApplicationCredentialRotated",
                aggregate_type="ApplicationCredential",
                aggregate_id=new_credential.credential_id,
                tenant_id=application.tenant_id,
                owner_id=application.owner_id,
                payload={
                    "old_credential_id": credential_id,
                    "new_credential_id": new_credential.credential_id,
                    "application_id": application.id,
                    "rotated_at": now.isoformat(),
                },
                audit_id=audit_id,
                occurred_at=now,
            )
            self._audit(
                uow,
                audit_id=audit_id,
                action="identity.rotate_credential",
                tenant_id=application.tenant_id,
                owner_id=application.owner_id,
                input_ids=(credential_id,),
                output_ids=(new_credential.credential_id,),
                event_ids=(event.event_id,),
                occurred_at=now,
            )
            uow.commit()
        return new_credential, plaintext

    def revoke_credential(self, credential_id: str) -> None:
        with self._uow as uow:
            credential = uow.identity.get_credential(credential_id)
            if credential is None:
                raise IdentityError(f"credential {credential_id!r} does not exist")
            application = self._require_application(uow, credential.application_id)
            now = utc_now()
            audit_id = new_id(AUDIT_PREFIX)
            uow.identity.set_credential_status(credential_id, CredentialStatus.REVOKED, now)
            event = self._event(
                uow,
                event_type="ApplicationCredentialRevoked",
                aggregate_type="ApplicationCredential",
                aggregate_id=credential_id,
                tenant_id=application.tenant_id,
                owner_id=application.owner_id,
                payload={
                    "credential_id": credential_id,
                    "application_id": application.id,
                    "revoked_at": now.isoformat(),
                },
                audit_id=audit_id,
                occurred_at=now,
            )
            self._audit(
                uow,
                audit_id=audit_id,
                action="identity.revoke_credential",
                tenant_id=application.tenant_id,
                owner_id=application.owner_id,
                input_ids=(credential_id,),
                output_ids=(),
                event_ids=(event.event_id,),
                occurred_at=now,
            )
            uow.commit()

    # ----------------------------------------------------------------- scopes

    def grant_scope(self, application_id: str, scope: PermissionScope) -> None:
        """Grant a scope. Only this governed CLI path can change scopes; an
        application/token can never grant scopes to itself over HTTP."""
        self._change_scope(application_id, scope, grant=True)

    def revoke_scope(self, application_id: str, scope: PermissionScope) -> None:
        self._change_scope(application_id, scope, grant=False)

    def _change_scope(self, application_id: str, scope: PermissionScope, grant: bool) -> None:
        with self._uow as uow:
            application = self._require_application(uow, application_id)
            current = set(uow.identity.get_application_scopes(application.id))
            if grant:
                current.add(scope.value)
            else:
                current.discard(scope.value)
            now = utc_now()
            audit_id = new_id(AUDIT_PREFIX)
            uow.identity.set_application_scopes(application.id, sorted(current))
            event_type = "PermissionGranted" if grant else "PermissionRevoked"
            timestamp_key = "granted_at" if grant else "revoked_at"
            event = self._event(
                uow,
                event_type=event_type,
                aggregate_type="Application",
                aggregate_id=application.id,
                tenant_id=application.tenant_id,
                owner_id=application.owner_id,
                payload={
                    "application_id": application.id,
                    "scope": scope.value,
                    timestamp_key: now.isoformat(),
                },
                audit_id=audit_id,
                occurred_at=now,
            )
            self._audit(
                uow,
                audit_id=audit_id,
                action=f"identity.{'grant' if grant else 'revoke'}_scope",
                tenant_id=application.tenant_id,
                owner_id=application.owner_id,
                input_ids=(application.id,),
                output_ids=(),
                event_ids=(event.event_id,),
                occurred_at=now,
            )
            uow.commit()
