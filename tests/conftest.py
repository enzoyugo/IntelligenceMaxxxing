"""Shared fixtures.

SQLite is used for fast hermetic tests. PostgreSQL-specific suites live under
tests/postgres and are gated by scripts/audit/run_postgres_gates.ps1.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from intelligence_maxxxing.api.app import create_app
from intelligence_maxxxing.config import EngineSettings
from intelligence_maxxxing.infrastructure.database import Base
from tests.fixtures.identity import BootstrappedIdentity, bootstrap_test_identity

REPO_ROOT = Path(__file__).resolve().parent.parent


def make_settings(database_url: str) -> EngineSettings:
    return EngineSettings(
        ENGINE_ENV="test",
        ENGINE_HOST="127.0.0.1",
        ENGINE_PORT=8100,
        ENGINE_VERSION="0.1.0",
        CONSTITUTION_VERSION="1.1",
        DATABASE_URL=database_url,
        LOG_LEVEL="WARNING",
        _env_file=None,
    )


@pytest.fixture()
def sqlite_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'engine_test.sqlite3'}"


@pytest.fixture()
def app(sqlite_url: str) -> Iterator[FastAPI]:
    application = create_app(make_settings(sqlite_url))
    Base.metadata.create_all(application.state.db_engine)
    yield application
    application.state.db_engine.dispose()


@pytest.fixture()
def identity(app: FastAPI) -> BootstrappedIdentity:
    return bootstrap_test_identity(app)


@pytest.fixture()
def client(app: FastAPI, identity: BootstrappedIdentity) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.headers.update(identity.auth_header)
        yield test_client


@pytest.fixture()
def broken_db_app(tmp_path: Path) -> Iterator[FastAPI]:
    """App pointing at a database that cannot accept connections."""
    unreachable = "postgresql+psycopg://nobody:nothing@127.0.0.1:1/broken?connect_timeout=1"
    application = create_app(make_settings(unreachable))
    yield application
    application.state.db_engine.dispose()


def valid_observation_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "domain_pack": "core",
        "subject": "sleep",
        "statement": "Slept 7.5 hours",
        "knowledge_class": "OBSERVED_FACT",
        "observed_by": "test-suite",
        "context": {"scope": "personal", "attributes": {}},
        "source_ids": [],
        "metadata": {"unit": "hours"},
    }
