"""ORM table definitions (internal only; never exposed as public contracts).

Designed for PostgreSQL. SQLite is used only in tests.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EngineEventRow(Base):
    """Append-only event log. Rows are inserted, never updated or deleted."""

    __tablename__ = "engine_events"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope",
            "idempotency_key",
            name="uq_engine_events_idempotency_scope_key",
        ),
        UniqueConstraint(
            "aggregate_type",
            "aggregate_id",
            "aggregate_version",
            name="uq_engine_events_aggregate_version",
        ),
    )

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    domain_pack: Mapped[str] = mapped_column(String(64), nullable=False, default="core")
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    audit_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_scope: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(256), nullable=True)


class AuditRecordRow(Base):
    """Append-only audit trail."""

    __tablename__ = "audit_records"

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    api_version: Mapped[str] = mapped_column(String(16), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    domain_pack: Mapped[str] = mapped_column(String(64), nullable=False, default="core")
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    input_object_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    output_object_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    event_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    health_state: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class IdempotencyKeyRow(Base):
    """Idempotency ledger mapping (scope, key) to the original accepted result."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("scope", "idempotency_key", name="uq_idempotency_scope_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    observation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_id: Mapped[str] = mapped_column(String(64), nullable=False)
