"""Migration tests: the initial Alembic migration applies from scratch."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from tests.conftest import REPO_ROOT


@pytest.fixture(autouse=True)
def _isolate_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """migrations/env.py prefers DATABASE_URL; tests must not inherit ambient values."""
    monkeypatch.delenv("DATABASE_URL", raising=False)


def _alembic_config(database_url: str) -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_initial_migration_applies_from_scratch(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'migration_test.sqlite3'}"
    command.upgrade(_alembic_config(database_url), "head")

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"engine_events", "audit_records", "idempotency_keys"} <= tables

        event_columns = {c["name"] for c in inspector.get_columns("engine_events")}
        assert {
            "event_id",
            "event_type",
            "aggregate_type",
            "aggregate_id",
            "aggregate_version",
            "domain_pack",
            "actor_type",
            "actor_id",
            "schema_version",
            "payload",
            "occurred_at",
            "recorded_at",
            "audit_id",
            "request_id",
            "idempotency_key",
        } <= event_columns
    finally:
        engine.dispose()


def test_migration_matches_orm_metadata(tmp_path: Path) -> None:
    """The migrated schema contains every table the ORM expects."""
    from intelligence_maxxxing.infrastructure.database import Base

    database_url = f"sqlite:///{tmp_path / 'migration_parity.sqlite3'}"
    command.upgrade(_alembic_config(database_url), "head")

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        migrated_tables = set(inspector.get_table_names()) - {"alembic_version"}
        orm_tables = set(Base.metadata.tables.keys())
        assert orm_tables == migrated_tables
    finally:
        engine.dispose()
