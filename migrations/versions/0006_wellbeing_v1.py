"""Wellbeing Intelligence V1 additive projection tables.

Revision ID: 0006_wellbeing_v1
Revises: 0005_stage3_1
Create Date: 2026-07-20

Additive only. Stores formula-versioned score/feature snapshots, baselines,
and optional human feedback. Ledger remains source of truth for observations;
these tables are rebuildable ANALYZE/EXPLAIN caches.
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_wellbeing_v1"
down_revision = "0005_stage3_1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wellbeing_formula_versions",
        sa.Column("formula_id", sa.String(64), primary_key=True),
        sa.Column("version", sa.String(16), primary_key=True),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "wellbeing_baselines",
        sa.Column("baseline_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("application_id", sa.String(64), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("formula_id", sa.String(64), nullable=False),
        sa.Column("formula_version", sa.String(16), nullable=False),
        sa.Column("features_json", sa.JSON(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("as_of_global_position", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_wellbeing_baselines_scope",
        "wellbeing_baselines",
        ["tenant_id", "owner_id", "application_id", "window_days"],
    )

    op.create_table(
        "wellbeing_feature_snapshots",
        sa.Column("feature_snapshot_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("application_id", sa.String(64), nullable=False),
        sa.Column("formula_id", sa.String(64), nullable=False),
        sa.Column("formula_version", sa.String(16), nullable=False),
        sa.Column("period_start", sa.String(32), nullable=False),
        sa.Column("period_end", sa.String(32), nullable=False),
        sa.Column("features_json", sa.JSON(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("missing_days", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("as_of_global_position", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_wellbeing_features_scope",
        "wellbeing_feature_snapshots",
        ["tenant_id", "owner_id", "application_id", "computed_at"],
    )

    op.create_table(
        "wellbeing_score_snapshots",
        sa.Column("score_snapshot_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("application_id", sa.String(64), nullable=False),
        sa.Column("formula_id", sa.String(64), nullable=False),
        sa.Column("formula_version", sa.String(16), nullable=False),
        sa.Column("feature_snapshot_id", sa.String(64), nullable=True),
        sa.Column("happiness", sa.Float(), nullable=True),
        sa.Column("stress", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("early_warning", sa.String(64), nullable=False),
        sa.Column("data_sufficiency", sa.String(64), nullable=False),
        sa.Column("contributors_json", sa.JSON(), nullable=False),
        sa.Column("suggested_actions_json", sa.JSON(), nullable=False),
        sa.Column("explanation_json", sa.JSON(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("as_of_global_position", sa.BigInteger(), nullable=True),
    )
    op.create_index(
        "ix_wellbeing_scores_scope",
        "wellbeing_score_snapshots",
        ["tenant_id", "owner_id", "application_id", "computed_at"],
    )

    op.create_table(
        "wellbeing_feedback",
        sa.Column("feedback_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("application_id", sa.String(64), nullable=False),
        sa.Column("score_snapshot_id", sa.String(64), nullable=True),
        sa.Column("rating", sa.String(32), nullable=False),
        sa.Column("note", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_wellbeing_feedback_scope",
        "wellbeing_feedback",
        ["tenant_id", "owner_id", "application_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_wellbeing_feedback_scope", table_name="wellbeing_feedback")
    op.drop_table("wellbeing_feedback")
    op.drop_index("ix_wellbeing_scores_scope", table_name="wellbeing_score_snapshots")
    op.drop_table("wellbeing_score_snapshots")
    op.drop_index("ix_wellbeing_features_scope", table_name="wellbeing_feature_snapshots")
    op.drop_table("wellbeing_feature_snapshots")
    op.drop_index("ix_wellbeing_baselines_scope", table_name="wellbeing_baselines")
    op.drop_table("wellbeing_baselines")
    op.drop_table("wellbeing_formula_versions")
