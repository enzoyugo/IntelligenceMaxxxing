"""Local administrative CLI. Non-interactive flags for safe automation."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from intelligence_maxxxing import API_VERSION
from intelligence_maxxxing.application.use_cases.epistemic_projections import (
    EpistemicProjectionRebuildService,
)
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
    IdentityAdminService,
    ProjectionRebuildService,
    IntegrityVerificationService,
    EpistemicProjectionRebuildService,
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
    epistemic = EpistemicProjectionRebuildService(
        uow=SqlAlchemyUnitOfWork(session_factory),
        engine_version=settings.engine_version,
        api_version=API_VERSION,
        health_provider=health,
    )
    return identity, projections, integrity, epistemic


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

    sub.add_parser(
        "verify-projections",
        help="Non-destructively verify accepted_observations against the ledger",
    )

    sub.add_parser(
        "rebuild-epistemic",
        help="Rebuild Stage 3 epistemic projections from engine_events",
    )
    sub.add_parser(
        "verify-epistemic",
        help="Non-destructively verify epistemic projections against the ledger",
    )

    for name, help_text in (
        ("inspect-stream", "Show a stream head and its integrity checkpoint"),
        ("verify-stream", "Run a FULL integrity verification of one stream"),
        ("unquarantine-stream", "Release a quarantined stream (ADMINISTER_ENGINE)"),
    ):
        p_stream = sub.add_parser(name, help=help_text)
        p_stream.add_argument("--tenant-id", required=True)
        p_stream.add_argument("--owner-id", required=True)
        p_stream.add_argument("--application-id", required=True)
        if name == "unquarantine-stream":
            p_stream.add_argument("--reason", required=True)

    args = parser.parse_args(argv)
    identity, projections, integrity, epistemic = _build_services()

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

    if args.command == "verify-projections":
        verify_report = projections.verify()
        print(
            f"projection={verify_report.projection_name} matches={verify_report.matches} "
            f"quarantined={verify_report.quarantined} live_rows={verify_report.live_rows} "
            f"shadow_rows={verify_report.shadow_rows} "
            f"live_checksum={verify_report.live_checksum} "
            f"shadow_checksum={verify_report.shadow_checksum}"
        )
        return 0 if verify_report.ok else 2

    if args.command == "rebuild-epistemic":
        result = epistemic.rebuild(from_scratch=True)
        print(
            f"projection={result.projection_name} version={result.projection_version} "
            f"scanned={result.events_scanned} rows={result.rows_written} "
            f"position={result.last_global_position} checksum={result.checksum}"
        )
        return 0

    if args.command == "verify-epistemic":
        verify_report = epistemic.verify()
        print(
            f"projection={verify_report.projection_name} matches={verify_report.matches} "
            f"quarantined={verify_report.quarantined} live_rows={verify_report.live_rows} "
            f"shadow_rows={verify_report.shadow_rows} "
            f"live_checksum={verify_report.live_checksum} "
            f"shadow_checksum={verify_report.shadow_checksum}"
        )
        return 0 if verify_report.ok else 2

    if args.command == "inspect-stream":
        head, checkpoint = integrity.inspect_stream(
            args.tenant_id, args.owner_id, args.application_id
        )
        if head is None:
            print("stream not found")
            return 2
        print(
            f"status={head.status} stream_version={head.stream_version} "
            f"last_event_id={head.last_event_id} head_hash={head.current_event_hash}"
        )
        if head.status == "QUARANTINED":
            print(
                f"quarantine_reason={head.quarantine_reason} "
                f"broken_event_id={head.broken_event_id} "
                f"quarantined_at={head.quarantined_at}"
            )
        if checkpoint is not None:
            print(
                f"checkpoint_position={checkpoint.last_verified_global_position} "
                f"checkpoint_hash={checkpoint.last_verified_hash}"
            )
        return 0

    if args.command == "verify-stream":
        stream_result = integrity.verify_stream(args.tenant_id, args.owner_id, args.application_id)
        print(
            f"ok={stream_result.ok} events_checked={stream_result.events_checked} "
            f"broken_event_id={stream_result.broken_event_id}"
        )
        return 0 if stream_result.ok else 2

    if args.command == "unquarantine-stream":
        released = integrity.unquarantine_stream(
            args.tenant_id,
            args.owner_id,
            args.application_id,
            reason=args.reason,
            admin_actor_id="constitutional-owner",
            actor_scopes=frozenset({PermissionScope.ADMINISTER_ENGINE.value}),
        )
        print(f"released={released.ok} events_checked={released.events_checked}")
        return 0 if released.ok else 2

    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
