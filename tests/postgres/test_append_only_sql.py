"""PostgreSQL append-only enforcement.

RUNTIME_ROLE_CANNOT_UPDATE_EVENT / DELETE_EVENT / TRUNCATE_EVENT /
RUNTIME_ROLE_CANNOT_UPDATE_AUDIT / DELETE_AUDIT
"""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from tests.conftest import valid_observation_payload

pytestmark = pytest.mark.postgres

RUNTIME_PASSWORD = "runtime_gate_password_not_for_prod"


def _ensure_runtime_password(admin_url: str) -> str:
    """Set a known password for engine_runtime for this gate run only."""
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text(f"ALTER ROLE engine_runtime PASSWORD '{RUNTIME_PASSWORD}'"))
    engine.dispose()
    # Swap user in the URL.
    # postgresql+psycopg://intelligence:intelligence@host/db
    return admin_url.replace(
        "://intelligence:intelligence@",
        f"://engine_runtime:{RUNTIME_PASSWORD}@",
        1,
    )


def _seed_event(pg_app: FastAPI, pg_client: TestClient) -> str:
    response = pg_client.post(
        "/api/v1/observations",
        json=valid_observation_payload(),
        headers={"Idempotency-Key": f"ao-{uuid.uuid4().hex}"},
    )
    assert response.status_code == 201
    return response.json()["data"]["event_id"]


def test_runtime_role_cannot_update_event(
    migrated_postgres: str, pg_app: FastAPI, pg_client: TestClient
) -> None:
    event_id = _seed_event(pg_app, pg_client)
    runtime_url = _ensure_runtime_password(migrated_postgres)
    engine = create_engine(runtime_url)
    try:
        with engine.connect() as conn, pytest.raises((DBAPIError, ProgrammingError)):
            conn.execute(
                text("UPDATE engine_events SET event_type = 'TAMPERED' WHERE event_id = :eid"),
                {"eid": event_id},
            )
            conn.commit()
    finally:
        engine.dispose()


def test_runtime_role_cannot_delete_event(
    migrated_postgres: str, pg_app: FastAPI, pg_client: TestClient
) -> None:
    event_id = _seed_event(pg_app, pg_client)
    runtime_url = _ensure_runtime_password(migrated_postgres)
    engine = create_engine(runtime_url)
    try:
        with engine.connect() as conn, pytest.raises((DBAPIError, ProgrammingError)):
            conn.execute(
                text("DELETE FROM engine_events WHERE event_id = :eid"),
                {"eid": event_id},
            )
            conn.commit()
    finally:
        engine.dispose()


def test_runtime_role_cannot_truncate_event(migrated_postgres: str) -> None:
    runtime_url = _ensure_runtime_password(migrated_postgres)
    engine = create_engine(runtime_url)
    try:
        with engine.connect() as conn, pytest.raises((DBAPIError, ProgrammingError)):
            conn.execute(text("TRUNCATE engine_events"))
            conn.commit()
    finally:
        engine.dispose()


def test_runtime_role_cannot_update_audit(
    migrated_postgres: str, pg_app: FastAPI, pg_client: TestClient
) -> None:
    response = pg_client.post(
        "/api/v1/observations",
        json=valid_observation_payload(),
        headers={"Idempotency-Key": f"ao-aud-{uuid.uuid4().hex}"},
    )
    audit_id = response.json()["data"]["audit_id"]
    runtime_url = _ensure_runtime_password(migrated_postgres)
    engine = create_engine(runtime_url)
    try:
        with engine.connect() as conn, pytest.raises((DBAPIError, ProgrammingError)):
            conn.execute(
                text("UPDATE audit_records SET action = 'TAMPERED' WHERE audit_id = :aid"),
                {"aid": audit_id},
            )
            conn.commit()
    finally:
        engine.dispose()


def test_runtime_role_cannot_delete_audit(
    migrated_postgres: str, pg_app: FastAPI, pg_client: TestClient
) -> None:
    response = pg_client.post(
        "/api/v1/observations",
        json=valid_observation_payload(),
        headers={"Idempotency-Key": f"ao-aud2-{uuid.uuid4().hex}"},
    )
    audit_id = response.json()["data"]["audit_id"]
    runtime_url = _ensure_runtime_password(migrated_postgres)
    engine = create_engine(runtime_url)
    try:
        with engine.connect() as conn, pytest.raises((DBAPIError, ProgrammingError)):
            conn.execute(
                text("DELETE FROM audit_records WHERE audit_id = :aid"),
                {"aid": audit_id},
            )
            conn.commit()
    finally:
        engine.dispose()
