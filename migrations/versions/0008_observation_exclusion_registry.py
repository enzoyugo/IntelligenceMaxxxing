"""Append-only observation exclusion registry (durable).

Revision ID: 0008_observation_exclusion
Revises: 0007_wellbeing_v2
Create Date: 2026-07-21

Never deletes ledger observations. Seeds the known SCALE_CONTRACT smoke
exclusion for personal-ledger integrity.
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_observation_exclusion"
down_revision = "0007_wellbeing_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "observation_exclusions",
        sa.Column("exclusion_id", sa.String(64), primary_key=True),
        sa.Column("target_observation_id", sa.String(64), nullable=False, index=True),
        sa.Column("reason_code", sa.String(128), nullable=False),
        sa.Column("reason", sa.String(4000), nullable=False),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_system", sa.String(128), nullable=False),
        sa.Column("evidence_report", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_observation_exclusions_target_unique",
        "observation_exclusions",
        ["target_observation_id"],
        unique=True,
    )
    # Seed known SCALE_CONTRACT smoke exclusion (append-only closeout).
    op.execute(
        sa.text(
            """
            INSERT INTO observation_exclusions (
              exclusion_id, target_observation_id, reason_code, reason,
              invalidated_at, actor_system, evidence_report, created_at
            ) VALUES (
              'excl_scale_contract_smoke_v1',
              'obs_ab746ef9d6c64732990a6e7fc4aaea15',
              'TEST_OBSERVATION_IN_PRODUCTION_LEDGER',
              'SCALE_CONTRACT_V1 smoke observation retained in personal ledger; excluded from personal wellbeing input selection.',
              '2026-07-21T00:00:00+00:00',
              'wellbeing_test_isolation_v1',
              'WELLBEING_EXISTING_SMOKE_CONTAMINATION_AUDIT_V1',
              '2026-07-21T00:00:00+00:00'
            )
            ON CONFLICT (target_observation_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_observation_exclusions_target_unique", table_name="observation_exclusions")
    op.drop_table("observation_exclusions")
