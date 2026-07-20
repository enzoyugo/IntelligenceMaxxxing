"""Wellbeing V2 SHADOW additive columns (preserve V1 snapshots).

Revision ID: 0007_wellbeing_v2
Revises: 0006_wellbeing_v1
Create Date: 2026-07-20

Does not rewrite historical V1 rows. New columns are nullable.
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_wellbeing_v2"
down_revision = "0006_wellbeing_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "wellbeing_score_snapshots",
        sa.Column("formula_status", sa.String(32), nullable=True),
    )
    op.add_column(
        "wellbeing_score_snapshots",
        sa.Column("input_fingerprint", sa.String(64), nullable=True),
    )
    op.add_column(
        "wellbeing_score_snapshots",
        sa.Column("change_state", sa.String(64), nullable=True),
    )
    op.add_column(
        "wellbeing_score_snapshots",
        sa.Column("happiness_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "wellbeing_score_snapshots",
        sa.Column("stress_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "wellbeing_score_snapshots",
        sa.Column("overall_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "wellbeing_score_snapshots",
        sa.Column("sub_scores_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "wellbeing_score_snapshots",
        sa.Column("plausible_range_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "wellbeing_score_snapshots",
        sa.Column("happiness_acute", sa.Float(), nullable=True),
    )
    op.add_column(
        "wellbeing_score_snapshots",
        sa.Column("happiness_chronic", sa.Float(), nullable=True),
    )
    op.add_column(
        "wellbeing_score_snapshots",
        sa.Column("stress_acute", sa.Float(), nullable=True),
    )
    op.add_column(
        "wellbeing_score_snapshots",
        sa.Column("stress_chronic", sa.Float(), nullable=True),
    )
    op.add_column(
        "wellbeing_score_snapshots",
        sa.Column("stress_anticipatory", sa.Float(), nullable=True),
    )
    op.add_column(
        "wellbeing_formula_versions",
        sa.Column("status", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("wellbeing_formula_versions", "status")
    for col in (
        "stress_anticipatory",
        "stress_chronic",
        "stress_acute",
        "happiness_chronic",
        "happiness_acute",
        "plausible_range_json",
        "sub_scores_json",
        "overall_confidence",
        "stress_confidence",
        "happiness_confidence",
        "change_state",
        "input_fingerprint",
        "formula_status",
    ):
        op.drop_column("wellbeing_score_snapshots", col)
