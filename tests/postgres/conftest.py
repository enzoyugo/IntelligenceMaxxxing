"""PostgreSQL-only fixtures. These tests refuse to run against SQLite."""

from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from intelligence_maxxxing.api.app import create_app
from intelligence_maxxxing.config import EngineSettings
from tests.conftest import REPO_ROOT, make_settings, valid_observation_payload
from tests.fixtures.identity import BootstrappedIdentity, bootstrap_test_identity

# Re-export for convenience.
__all__ = ["valid_observation_payload"]


def _require_postgres_url() -> str:
    import os

    if os.environ.get("ENGINE_RUN_POSTGRES_GATES") != "1":
        pytest.skip(
            "PostgreSQL gates require ENGINE_RUN_POSTGRES_GATES=1 "
            "(set by scripts/audit/run_postgres_gates.ps1). No SQLite fallback."
        )
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip(
            "PostgreSQL gates require DATABASE_URL pointing at real PostgreSQL. No SQLite fallback."
        )
    return url


@pytest.fixture(scope="session")
def postgres_url() -> str:
    return _require_postgres_url()


@pytest.fixture(scope="session")
def migrated_postgres(postgres_url: str) -> Iterator[str]:
    """Apply Alembic migrations from zero against the gate database."""
    # Wipe public schema so each session starts clean.
    engine = create_engine(postgres_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()

    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", postgres_url)
    command.upgrade(config, "head")
    yield postgres_url


@pytest.fixture()
def pg_app(migrated_postgres: str) -> Iterator[FastAPI]:
    application = create_app(make_settings(migrated_postgres))
    yield application
    application.state.db_engine.dispose()


@pytest.fixture()
def pg_identity(pg_app: FastAPI) -> BootstrappedIdentity:
    return bootstrap_test_identity(pg_app)


@pytest.fixture()
def pg_client(pg_app: FastAPI, pg_identity: BootstrappedIdentity) -> Iterator[TestClient]:
    with TestClient(pg_app, raise_server_exceptions=False) as client:
        client.headers.update(pg_identity.auth_header)
        yield client


@pytest.fixture()
def pg_settings(migrated_postgres: str) -> EngineSettings:
    return make_settings(migrated_postgres)
