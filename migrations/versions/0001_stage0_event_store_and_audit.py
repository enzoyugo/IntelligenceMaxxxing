"""Stage 0: append-only event store, audit trail and idempotency ledger.

Revision ID: 0001_stage0
Revises:
Create Date: 2026-07-19

"""

import sqlalchemy as sa
from alembic import op

revision = "0001_stage0"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "engine_events",
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_id", sa.String(length=64), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("domain_pack", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("audit_id", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_scope", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=256), nullable=True),
        sa.UniqueConstraint(
            "idempotency_scope",
            "idempotency_key",
            name="uq_engine_events_idempotency_scope_key",
        ),
        sa.UniqueConstraint(
            "aggregate_type",
            "aggregate_id",
            "aggregate_version",
            name="uq_engine_events_aggregate_version",
        ),
    )
    op.create_index("ix_engine_events_event_type", "engine_events", ["event_type"])
    op.create_index("ix_engine_events_aggregate_id", "engine_events", ["aggregate_id"])
    op.create_index("ix_engine_events_audit_id", "engine_events", ["audit_id"])

    op.create_table(
        "audit_records",
        sa.Column("audit_id", sa.String(length=64), primary_key=True),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("engine_version", sa.String(length=32), nullable=False),
        sa.Column("api_version", sa.String(length=16), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("domain_pack", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("input_object_ids", sa.JSON(), nullable=False),
        sa.Column("output_object_ids", sa.JSON(), nullable=False),
        sa.Column("event_ids", sa.JSON(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("health_state", sa.JSON(), nullable=False),
    )
    op.create_index("ix_audit_records_request_id", "audit_records", ["request_id"])

    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scope", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("observation_id", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("audit_id", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("scope", "idempotency_key", name="uq_idempotency_scope_key"),
    )


def downgrade() -> None:
    # History is append-only by constitution; downgrading drops empty Stage 0
    # structures only and must never be run against real recorded history.
    op.drop_table("idempotency_keys")
    op.drop_index("ix_audit_records_request_id", table_name="audit_records")
    op.drop_table("audit_records")
    op.drop_index("ix_engine_events_audit_id", table_name="engine_events")
    op.drop_index("ix_engine_events_aggregate_id", table_name="engine_events")
    op.drop_index("ix_engine_events_event_type", table_name="engine_events")
    op.drop_table("engine_events")
