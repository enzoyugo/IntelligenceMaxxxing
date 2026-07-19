"""PostgreSQL core gates.

POSTGRES_MIGRATION_FROM_ZERO_PASS / POSTGRES_SCHEMA_MATCHES_ORM /
POSTGRES_JSON_AND_UTC_PASS / POSTGRES_TRANSACTION_ROLLBACK_PASS
"""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from intelligence_maxxxing.infrastructure.database import Base
from tests.conftest import valid_observation_payload

pytestmark = pytest.mark.postgres


def test_postgres_migration_from_zero_pass(migrated_postgres: str) -> None:
    engine = create_engine(migrated_postgres)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {
            "engine_events",
            "audit_records",
            "idempotency_keys",
            "tenants",
            "users",
            "applications",
            "application_credentials",
            "accepted_observations",
            "projection_checkpoints",
        } <= tables
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version()")).scalar_one()
        assert "PostgreSQL 16" in str(version)
    finally:
        engine.dispose()


def test_postgres_schema_matches_orm(migrated_postgres: str) -> None:
    engine = create_engine(migrated_postgres)
    try:
        inspector = inspect(engine)
        migrated = set(inspector.get_table_names()) - {"alembic_version"}
        orm = set(Base.metadata.tables.keys())
        assert orm == migrated
    finally:
        engine.dispose()


def test_postgres_json_and_utc_pass(pg_app: FastAPI, pg_client: TestClient) -> None:
    payload = valid_observation_payload()
    payload["occurred_at"] = "2026-07-19T12:00:00+00:00"
    payload["metadata"] = {"unit": "hours", "nested_ok": True}
    response = pg_client.post(
        "/api/v1/observations",
        json=payload,
        headers={"Idempotency-Key": f"pg-json-{uuid.uuid4().hex}"},
    )
    assert response.status_code == 201
    audit_id = response.json()["data"]["audit_id"]
    audit = pg_client.get(f"/api/v1/audits/{audit_id}").json()["data"]
    event = audit["events"][0]
    assert event["payload"]["metadata"]["unit"] == "hours"
    assert event["occurred_at"].startswith("2026-07-19T12:00:00")
    # Health snapshot is nested JSON with measured components.
    assert "snapshot_id" in audit["health_state"]
    assert "components" in audit["health_state"]


def test_postgres_transaction_rollback_pass(pg_app: FastAPI) -> None:
    engine = pg_app.state.db_engine
    with engine.connect() as conn:
        trans = conn.begin()
        conn.execute(
            text(
                "INSERT INTO tenants (id, schema_version, status, display_name, "
                "created_at, meta, audit_id) VALUES "
                "('tnt_rollback', '1.0', 'ACTIVE', 'Rollback', :ts, '{}'::json, 'aud_rb')"
            ),
            {"ts": datetime.now(UTC)},
        )
        trans.rollback()
        count = conn.execute(
            text("SELECT count(*) FROM tenants WHERE id = 'tnt_rollback'")
        ).scalar_one()
        assert count == 0
