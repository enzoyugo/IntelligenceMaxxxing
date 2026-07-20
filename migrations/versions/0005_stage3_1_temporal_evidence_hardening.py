"""Stage 3.1: temporal anchors, evidence fingerprint, terminal fields.

Revision ID: 0005_stage3_1
Revises: 0004_stage3
Create Date: 2026-07-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_stage3_1"
down_revision = "0004_stage3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "current_experiments",
        sa.Column("activation_event_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "current_experiments",
        sa.Column("activation_global_position", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "current_experiments",
        sa.Column("activation_recorded_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "evidence_snapshots",
        sa.Column("evidence_fingerprint", sa.String(64), nullable=True),
    )
    op.add_column(
        "evidence_snapshots",
        sa.Column("evidence_cutoff_global_position", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "evidence_snapshots",
        sa.Column("evidence_cutoff_recorded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "evidence_snapshots",
        sa.Column("evaluation_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "evidence_snapshots",
        sa.Column("evaluation_kind", sa.String(32), nullable=True),
    )
    op.add_column(
        "evidence_snapshots",
        sa.Column("terminal", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "evidence_snapshots",
        sa.Column("terminal_reason", sa.String(64), nullable=True),
    )
    op.add_column(
        "evidence_snapshots",
        sa.Column("critical_data_quality_failure", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "evidence_snapshots",
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "evidence_snapshots",
        sa.Column("first_source_global_position", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "evidence_snapshots",
        sa.Column("last_source_global_position", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ux_evidence_fingerprint",
        "evidence_snapshots",
        [
            "tenant_id",
            "owner_id",
            "application_id",
            "experiment_id",
            "phase",
            "evidence_fingerprint",
        ],
        unique=True,
        postgresql_where=sa.text("evidence_fingerprint IS NOT NULL"),
        sqlite_where=sa.text("evidence_fingerprint IS NOT NULL"),
    )

    op.add_column(
        "experiment_progress",
        sa.Column("target_remaining", sa.Integer(), nullable=True),
    )
    op.add_column(
        "experiment_progress",
        sa.Column("sufficient_remaining", sa.Integer(), nullable=True),
    )
    op.add_column(
        "experiment_progress",
        sa.Column("below_remaining", sa.Integer(), nullable=True),
    )
    op.add_column(
        "experiment_progress",
        sa.Column("future_excluded", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "experiment_progress",
        sa.Column("duplicate_source_excluded", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "experiment_progress",
        sa.Column("critical_data_quality_failure", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "experiment_progress",
        sa.Column("evaluation_kind", sa.String(32), nullable=True),
    )
    op.add_column(
        "experiment_progress",
        sa.Column("terminal", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "experiment_progress",
        sa.Column("terminal_reason", sa.String(64), nullable=True),
    )
    op.add_column(
        "experiment_progress",
        sa.Column("minimum_group_size", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("experiment_progress", "minimum_group_size")
    op.drop_column("experiment_progress", "terminal_reason")
    op.drop_column("experiment_progress", "terminal")
    op.drop_column("experiment_progress", "evaluation_kind")
    op.drop_column("experiment_progress", "critical_data_quality_failure")
    op.drop_column("experiment_progress", "duplicate_source_excluded")
    op.drop_column("experiment_progress", "future_excluded")
    op.drop_column("experiment_progress", "below_remaining")
    op.drop_column("experiment_progress", "sufficient_remaining")
    op.drop_column("experiment_progress", "target_remaining")
    op.drop_index("ux_evidence_fingerprint", table_name="evidence_snapshots")
    for col in (
        "last_source_global_position",
        "first_source_global_position",
        "source_count",
        "critical_data_quality_failure",
        "terminal_reason",
        "terminal",
        "evaluation_kind",
        "evaluation_started_at",
        "evidence_cutoff_recorded_at",
        "evidence_cutoff_global_position",
        "evidence_fingerprint",
    ):
        op.drop_column("evidence_snapshots", col)
    op.drop_column("current_experiments", "activation_recorded_at")
    op.drop_column("current_experiments", "activation_global_position")
    op.drop_column("current_experiments", "activation_event_id")
