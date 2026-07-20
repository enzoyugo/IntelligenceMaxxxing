"""Stage 3: first epistemic loop projection tables.

Revision ID: 0004_stage3
Revises: 0003_stage1_1
Create Date: 2026-07-19

Adds rebuildable derived tables for hypotheses, experiments, beliefs,
evidence snapshots, experiment progress and learning history. The ledger
(`engine_events` / `audit_records`) remains the primary source of truth.
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_stage3"
down_revision = "0003_stage1_1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "current_hypotheses",
        sa.Column("hypothesis_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("application_id", sa.String(64), nullable=False),
        sa.Column("domain_pack", sa.String(64), nullable=False),
        sa.Column("template_id", sa.String(128), nullable=False),
        sa.Column("template_version", sa.String(16), nullable=False),
        sa.Column("statement", sa.String(4000), nullable=False),
        sa.Column("direction", sa.String(32), nullable=False),
        sa.Column("causality_level", sa.String(64), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("human_confirmed", sa.Integer(), nullable=False),
        sa.Column("parameters_json", sa.JSON(), nullable=True),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("experiment_id", sa.String(64), nullable=True),
        sa.Column("audit_id", sa.String(64), nullable=False),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("global_position", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_current_hypotheses_scope", "current_hypotheses", ["tenant_id", "owner_id", "application_id"])

    op.create_table(
        "current_experiments",
        sa.Column("experiment_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("application_id", sa.String(64), nullable=False),
        sa.Column("hypothesis_id", sa.String(64), nullable=False),
        sa.Column("protocol_version", sa.String(16), nullable=False),
        sa.Column("analysis_method", sa.String(128), nullable=False),
        sa.Column("baseline_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prospective_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prospective_target", sa.Integer(), nullable=False),
        sa.Column("maximum_window_days", sa.Integer(), nullable=False),
        sa.Column("minimum_group_size", sa.Integer(), nullable=False),
        sa.Column("minimum_meaningful_difference", sa.Float(), nullable=False),
        sa.Column("sleep_threshold_hours", sa.Float(), nullable=False),
        sa.Column("random_seed_policy", sa.String(256), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("pre_registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("audit_id", sa.String(64), nullable=False),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("global_position", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_current_experiments_scope", "current_experiments", ["tenant_id", "owner_id", "application_id"])
    op.create_index("ix_current_experiments_hypothesis", "current_experiments", ["hypothesis_id"])

    op.create_table(
        "belief_snapshots",
        sa.Column("belief_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("application_id", sa.String(64), nullable=False),
        sa.Column("hypothesis_id", sa.String(64), nullable=False),
        sa.Column("evidence_id", sa.String(64), nullable=False),
        sa.Column("previous_belief_id", sa.String(64), nullable=True),
        sa.Column("belief_state", sa.String(64), nullable=False),
        sa.Column("model_probability", sa.Float(), nullable=False),
        sa.Column("credible_interval_low", sa.Float(), nullable=False),
        sa.Column("credible_interval_high", sa.Float(), nullable=False),
        sa.Column("estimated_effect", sa.Float(), nullable=False),
        sa.Column("minimum_meaningful_difference", sa.Float(), nullable=False),
        sa.Column("data_confidence", sa.String(32), nullable=False),
        sa.Column("method_confidence", sa.String(32), nullable=False),
        sa.Column("conclusion_confidence", sa.String(32), nullable=False),
        sa.Column("recommendation_confidence", sa.String(32), nullable=False),
        sa.Column("calibration_state", sa.String(32), nullable=False),
        sa.Column("causality_level", sa.String(64), nullable=False),
        sa.Column("limitations_json", sa.JSON(), nullable=False),
        sa.Column("is_current", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("audit_id", sa.String(64), nullable=False),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("global_position", sa.BigInteger(), nullable=False),
    )
    op.create_index(
        "ix_belief_snapshots_hypothesis",
        "belief_snapshots",
        ["tenant_id", "owner_id", "application_id", "hypothesis_id"],
    )

    op.create_table(
        "evidence_snapshots",
        sa.Column("evidence_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("application_id", sa.String(64), nullable=False),
        sa.Column("hypothesis_id", sa.String(64), nullable=False),
        sa.Column("experiment_id", sa.String(64), nullable=False),
        sa.Column("phase", sa.String(64), nullable=False),
        sa.Column("source_observation_ids", sa.JSON(), nullable=False),
        sa.Column("source_event_ids", sa.JSON(), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("eligible_count", sa.Integer(), nullable=False),
        sa.Column("excluded_count", sa.Integer(), nullable=False),
        sa.Column("exclusion_reasons", sa.JSON(), nullable=False),
        sa.Column("group_counts", sa.JSON(), nullable=False),
        sa.Column("descriptive_statistics", sa.JSON(), nullable=False),
        sa.Column("analysis_parameters", sa.JSON(), nullable=False),
        sa.Column("analysis_result", sa.JSON(), nullable=True),
        sa.Column("confounding_diagnostics", sa.JSON(), nullable=False),
        sa.Column("limitations_json", sa.JSON(), nullable=False),
        sa.Column("belief_state", sa.String(64), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("audit_id", sa.String(64), nullable=False),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("global_position", sa.BigInteger(), nullable=False),
    )
    op.create_index(
        "ix_evidence_snapshots_source_hash",
        "evidence_snapshots",
        ["experiment_id", "phase", "source_hash"],
    )

    op.create_table(
        "experiment_progress",
        sa.Column("experiment_id", sa.String(64), primary_key=True),
        sa.Column("hypothesis_id", sa.String(64), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("application_id", sa.String(64), nullable=False),
        sa.Column("baseline_eligible", sa.Integer(), nullable=False),
        sa.Column("baseline_sufficient", sa.Integer(), nullable=False),
        sa.Column("baseline_below", sa.Integer(), nullable=False),
        sa.Column("prospective_eligible", sa.Integer(), nullable=False),
        sa.Column("prospective_sufficient", sa.Integer(), nullable=False),
        sa.Column("prospective_below", sa.Integer(), nullable=False),
        sa.Column("prospective_target", sa.Integer(), nullable=False),
        sa.Column("window_days_remaining", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("current_belief_state", sa.String(64), nullable=True),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "learning_history",
        sa.Column("learning_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("application_id", sa.String(64), nullable=False),
        sa.Column("hypothesis_id", sa.String(64), nullable=False),
        sa.Column("previous_belief_id", sa.String(64), nullable=True),
        sa.Column("new_belief_id", sa.String(64), nullable=False),
        sa.Column("outcome_evaluation_id", sa.String(64), nullable=False),
        sa.Column("change_type", sa.String(64), nullable=False),
        sa.Column("what_changed", sa.String(2000), nullable=False),
        sa.Column("why_changed", sa.String(2000), nullable=False),
        sa.Column("what_remains_unknown", sa.String(2000), nullable=False),
        sa.Column("next_evidence_needed", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("audit_id", sa.String(64), nullable=False),
        sa.Column("event_id", sa.String(64), nullable=False),
        sa.Column("global_position", sa.BigInteger(), nullable=False),
    )
    op.create_index(
        "ix_learning_history_hypothesis",
        "learning_history",
        ["tenant_id", "owner_id", "application_id", "hypothesis_id"],
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in (
            "current_hypotheses",
            "current_experiments",
            "belief_snapshots",
            "evidence_snapshots",
            "experiment_progress",
            "learning_history",
        ):
            op.execute(
                sa.text(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO engine_runtime"
                )
            )
            op.execute(sa.text(f"GRANT SELECT ON {table} TO engine_readonly"))


def downgrade() -> None:
    for table in (
        "learning_history",
        "experiment_progress",
        "evidence_snapshots",
        "belief_snapshots",
        "current_experiments",
        "current_hypotheses",
    ):
        op.drop_table(table)
