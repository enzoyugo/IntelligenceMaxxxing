"""Destructive downgrade safety.

DESTRUCTIVE_DOWNGRADE_BLOCKED_BY_DEFAULT /
DESTRUCTIVE_DOWNGRADE_REQUIRES_BACKUP_ID /
DESTRUCTIVE_DOWNGRADE_REQUIRES_ADMIN
"""

from intelligence_maxxxing.application.use_cases.integrity import (
    REQUIRED_CONFIRM_PHRASE,
    MigrationSafetyPolicy,
    MigrationSafetyRequest,
)


def test_destructive_downgrade_blocked_by_default() -> None:
    blockers = MigrationSafetyPolicy().authorize(MigrationSafetyRequest())
    assert blockers
    assert any("DESTRUCTIVE_MIGRATIONS_ALLOWED" in b for b in blockers)


def test_destructive_downgrade_requires_backup_id() -> None:
    blockers = MigrationSafetyPolicy().authorize(
        MigrationSafetyRequest(
            destructive_migrations_allowed=True,
            maintenance_mode=True,
            confirmed_backup_id=None,
            actor_has_administer=True,
            confirm_phrase=REQUIRED_CONFIRM_PHRASE,
        )
    )
    assert any("BACKUP_ID" in b for b in blockers)


def test_destructive_downgrade_requires_admin() -> None:
    blockers = MigrationSafetyPolicy().authorize(
        MigrationSafetyRequest(
            destructive_migrations_allowed=True,
            maintenance_mode=True,
            confirmed_backup_id="backup-verified-001",
            actor_has_administer=False,
            confirm_phrase=REQUIRED_CONFIRM_PHRASE,
        )
    )
    assert any("ADMINISTER_ENGINE" in b for b in blockers)


def test_authorized_empty_environment_may_proceed() -> None:
    blockers = MigrationSafetyPolicy().authorize(
        MigrationSafetyRequest(
            destructive_migrations_allowed=True,
            maintenance_mode=True,
            confirmed_backup_id="backup-verified-001",
            actor_has_administer=True,
            confirm_phrase=REQUIRED_CONFIRM_PHRASE,
        )
    )
    assert blockers == []
