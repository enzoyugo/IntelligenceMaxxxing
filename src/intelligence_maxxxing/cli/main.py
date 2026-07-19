"""Local administrative CLI. Non-interactive flags for safe automation."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from intelligence_maxxxing import API_VERSION
from intelligence_maxxxing.application.use_cases.identity_admin import IdentityAdminService
from intelligence_maxxxing.application.use_cases.integrity import (
    IntegrityVerificationService,
    LoggingIntegrityViolationHook,
)
from intelligence_maxxxing.application.use_cases.projections import ProjectionRebuildService
from intelligence_maxxxing.config import get_settings
from intelligence_maxxxing.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from intelligence_maxxxing.infrastructure.health import (
    MeasuredHealthSnapshotProvider,
    SqlAlchemyDatabaseHealth,
)
from intelligence_maxxxing.infrastructure.repositories import SqlAlchemyUnitOfWork
from intelligence_maxxxing.permissions import PermissionScope


def _build_services() -> tuple[
    IdentityAdminService, ProjectionRebuildService, IntegrityVerificationService
]:
    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    db_health = SqlAlchemyDatabaseHealth(engine)
    health = MeasuredHealthSnapshotProvider(db_health, check_manifest=False)
    uow = SqlAlchemyUnitOfWork(session_factory)
    identity = IdentityAdminService(
        uow=uow,
        engine_version=settings.engine_version,
        api_version=API_VERSION,
        health_provider=health,
    )
    projections = ProjectionRebuildService(
        uow=SqlAlchemyUnitOfWork(session_factory),
        engine_version=settings.engine_version,
        api_version=API_VERSION,
        health_provider=health,
    )
    integrity = IntegrityVerificationService(
        uow=SqlAlchemyUnitOfWork(session_factory),
        engine_version=settings.engine_version,
        api_version=API_VERSION,
        health_provider=health,
        violation_hook=LoggingIntegrityViolationHook(),
    )
    return identity, projections, integrity


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="intelligence_maxxxing.cli",
        description="Governed local administration for IntelligenceMaxxxing",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_boot = sub.add_parser("bootstrap-owner", help="Create the private tenant and owner user")
    p_boot.add_argument("--tenant-name", required=True)
    p_boot.add_argument("--owner-name", required=True)

    p_reg = sub.add_parser("register-application", help="Register an application for an owner")
    p_reg.add_argument("--display-name", required=True)
    p_reg.add_argument("--owner-id", required=True)

    p_cred = sub.add_parser(
        "create-credential", help="Create an API credential (secret shown once)"
    )
    p_cred.add_argument("--application-id", required=True)
    p_cred.add_argument("--expires-at", default=None, help="ISO-8601 UTC expiration (optional)")

    p_rot = sub.add_parser("rotate-credential", help="Revoke old credential and issue a new one")
    p_rot.add_argument("--credential-id", required=True)

    p_rev = sub.add_parser("revoke-credential", help="Revoke a credential")
    p_rev.add_argument("--credential-id", required=True)

    p_grant = sub.add_parser("grant-scope", help="Grant a permission scope to an application")
    p_grant.add_argument("--application-id", required=True)
    p_grant.add_argument("--scope", required=True, choices=[s.value for s in PermissionScope])

    sub.add_parser("list-applications", help="List registered applications")

    p_int = sub.add_parser("verify-integrity", help="Verify the event integrity chain")
    p_int.add_argument("--mode", choices=["FULL", "INCREMENTAL"], default="FULL")

    p_proj = sub.add_parser("rebuild-projections", help="Rebuild accepted_observations from events")
    p_proj.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint instead of rebuilding from scratch",
    )

    args = parser.parse_args(argv)
    identity, projections, integrity = _build_services()

    if args.command == "bootstrap-owner":
        tenant, user = identity.bootstrap_owner(args.tenant_name, args.owner_name)
        print(f"tenant_id={tenant.id}")
        print(f"owner_id={user.id}")
        return 0

    if args.command == "register-application":
        app = identity.register_application(args.display_name, args.owner_id)
        print(f"application_id={app.id}")
        print(f"owner_id={app.owner_id}")
        print(f"tenant_id={app.tenant_id}")
        return 0

    if args.command == "create-credential":
        expires = datetime.fromisoformat(args.expires_at) if args.expires_at else None
        credential, secret = identity.create_credential(args.application_id, expires)
        print(f"credential_id={credential.credential_id}")
        print(f"secret={secret}")
        print("Store the secret now; it will never be shown again.")
        return 0

    if args.command == "rotate-credential":
        credential, secret = identity.rotate_credential(args.credential_id)
        print(f"credential_id={credential.credential_id}")
        print(f"secret={secret}")
        print("Store the secret now; it will never be shown again.")
        return 0

    if args.command == "revoke-credential":
        identity.revoke_credential(args.credential_id)
        print(f"revoked={args.credential_id}")
        return 0

    if args.command == "grant-scope":
        identity.grant_scope(args.application_id, PermissionScope(args.scope))
        print(f"granted={args.scope} application_id={args.application_id}")
        return 0

    if args.command == "list-applications":
        for app in identity.list_applications():
            print(
                f"application_id={app.id} owner_id={app.owner_id} "
                f"status={app.status.value} display_name={app.display_name}"
            )
        return 0

    if args.command == "verify-integrity":
        report = integrity.verify(mode=args.mode)
        print(
            f"ok={report.ok} streams={report.streams_checked} "
            f"events={report.events_checked} violations={len(report.violations)}"
        )
        for violation in report.violations:
            print(
                f"violation owner={violation.owner_id} "
                f"app={violation.application_id} event={violation.broken_event_id}"
            )
        return 0 if report.ok else 2

    if args.command == "rebuild-projections":
        result = projections.rebuild(from_scratch=not args.resume)
        print(
            f"projection={result.projection_name} version={result.projection_version} "
            f"scanned={result.events_scanned} rows={result.rows_written} "
            f"position={result.last_global_position} checksum={result.checksum}"
        )
        return 0

    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
