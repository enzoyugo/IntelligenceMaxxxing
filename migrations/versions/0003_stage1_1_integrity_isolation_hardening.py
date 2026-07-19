"""Stage 1.1: application-scoped aggregates, stream heads, integrity checkpoints,
shadow projection and quarantine state.

Revision ID: 0003_stage1_1
Revises: 0002_stage1
Create Date: 2026-07-19

Does NOT alter the hashes of 0001_stage0 or 0002_stage1. Adds:
- `event_stream_heads`: transactional per-(tenant, owner, application) chain
  head with a QUARANTINED kill-switch state;
- `integrity_checkpoints`: last reliably verified point per stream (anchor for
  INCREMENTAL verification);
- `accepted_observations_shadow`: staging table for non-destructive projection
  verify and atomic promote;
- application-scoped aggregate uniqueness on `engine_events`.

Runtime role: may INSERT events and may UPDATE stream heads / integrity
checkpoints through the governed application paths, but never modifies events
or audits and never DELETEs a stream head (quarantine release is app-gated).
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_stage1_1"
down_revision = "0002_stage1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    _create_stream_heads()
    _create_integrity_checkpoints()
    _create_shadow_projection()
    _rescope_aggregate_constraint(is_postgres)

    if is_postgres:
        _install_protections_and_grants()


def _create_stream_heads() -> None:
    op.create_table(
        "event_stream_heads",
        sa.Column("tenant_id", sa.String(length=64), primary_key=True),
        sa.Column("owner_id", sa.String(length=64), primary_key=True),
        sa.Column("application_id", sa.String(length=64), primary_key=True),
        sa.Column("last_global_position", sa.BigInteger(), nullable=False),
        sa.Column("last_event_id", sa.String(length=64), nullable=True),
        sa.Column("current_event_hash", sa.String(length=64), nullable=True),
        sa.Column("stream_version", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("quarantine_reason", sa.String(length=512), nullable=True),
        sa.Column("broken_event_id", sa.String(length=64), nullable=True),
        sa.Column("quarantined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quarantine_audit_id", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def _create_integrity_checkpoints() -> None:
    op.create_table(
        "integrity_checkpoints",
        sa.Column("tenant_id", sa.String(length=64), primary_key=True),
        sa.Column("owner_id", sa.String(length=64), primary_key=True),
        sa.Column("application_id", sa.String(length=64), primary_key=True),
        sa.Column("last_verified_global_position", sa.BigInteger(), nullable=False),
        sa.Column("last_verified_event_id", sa.String(length=64), nullable=True),
        sa.Column("last_verified_hash", sa.String(length=64), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
    )


def _create_shadow_projection() -> None:
    op.create_table(
        "accepted_observations_shadow",
        sa.Column("observation_id", sa.String(length=64), primary_key=True),
        sa.Column("global_position", sa.BigInteger(), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("application_id", sa.String(length=64), nullable=False),
        sa.Column("domain_pack", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("statement", sa.String(length=4000), nullable=False),
        sa.Column("knowledge_class", sa.String(length=64), nullable=False),
        sa.Column("unknown_reason", sa.String(length=64), nullable=True),
        sa.Column("observed_by", sa.String(length=256), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("source_ids", sa.JSON(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("audit_id", sa.String(length=64), nullable=False),
    )
    op.create_index(
        "ix_accepted_observations_shadow_global_position",
        "accepted_observations_shadow",
        ["global_position"],
    )
    op.create_index(
        "ix_accepted_observations_shadow_owner_id",
        "accepted_observations_shadow",
        ["owner_id"],
    )
    op.create_index(
        "ix_accepted_observations_shadow_application_id",
        "accepted_observations_shadow",
        ["application_id"],
    )
    op.create_index(
        "ix_accepted_observations_shadow_domain_pack",
        "accepted_observations_shadow",
        ["domain_pack"],
    )


def _rescope_aggregate_constraint(is_postgres: bool) -> None:
    """Aggregate identity becomes (tenant, owner, application, type, id, version).

    Strictly looser than the old (type, id, version) constraint, so no existing
    row can conflict during the swap.
    """
    if is_postgres:
        op.execute(
            sa.text(
                "ALTER TABLE engine_events DROP CONSTRAINT "
                "IF EXISTS uq_engine_events_aggregate_version"
            )
        )
        op.create_unique_constraint(
            "uq_engine_events_aggregate_version",
            "engine_events",
            [
                "tenant_id",
                "owner_id",
                "application_id",
                "aggregate_type",
                "aggregate_id",
                "aggregate_version",
            ],
        )
    else:
        with op.batch_alter_table("engine_events") as batch:
            batch.drop_constraint(
                "uq_engine_events_aggregate_version", type_="unique"
            )
            batch.create_unique_constraint(
                "uq_engine_events_aggregate_version",
                [
                    "tenant_id",
                    "owner_id",
                    "application_id",
                    "aggregate_type",
                    "aggregate_id",
                    "aggregate_version",
                ],
            )


def _install_protections_and_grants() -> None:
    # Control state: never DELETE/TRUNCATE stream heads or integrity
    # checkpoints (UPDATE is allowed; that is how heads advance and quarantines
    # are set/released through governed paths).
    for table in ("event_stream_heads", "integrity_checkpoints"):
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER trg_{table}_forbid_delete
                BEFORE DELETE ON {table}
                FOR EACH ROW EXECUTE FUNCTION engine_reject_mutation();
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER trg_{table}_forbid_truncate
                BEFORE TRUNCATE ON {table}
                FOR EACH STATEMENT EXECUTE FUNCTION engine_reject_mutation();
                """
            )
        )

    # Runtime grants: heads/checkpoints are updatable control state; shadow is
    # disposable staging (full DML). Readonly may only read.
    for table in ("event_stream_heads", "integrity_checkpoints"):
        op.execute(sa.text(f"GRANT SELECT, INSERT, UPDATE ON {table} TO engine_runtime"))
        op.execute(sa.text(f"REVOKE DELETE, TRUNCATE ON {table} FROM engine_runtime"))
        op.execute(sa.text(f"GRANT SELECT ON {table} TO engine_readonly"))

    op.execute(
        sa.text(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON accepted_observations_shadow "
            "TO engine_runtime"
        )
    )
    op.execute(
        sa.text("GRANT SELECT ON accepted_observations_shadow TO engine_readonly")
    )


def downgrade() -> None:
    """Destructive: drops Stage 1.1 structures. Blocked by MigrationSafetyPolicy
    unless all safety flags, backup ID and ADMINISTER_ENGINE are present."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        for table in ("event_stream_heads", "integrity_checkpoints"):
            for op_name in ("delete", "truncate"):
                op.execute(
                    sa.text(f"DROP TRIGGER IF EXISTS trg_{table}_forbid_{op_name} ON {table}")
                )

    _rescope_aggregate_constraint_down(is_postgres)

    op.drop_table("accepted_observations_shadow")
    op.drop_table("integrity_checkpoints")
    op.drop_table("event_stream_heads")


def _rescope_aggregate_constraint_down(is_postgres: bool) -> None:
    if is_postgres:
        op.execute(
            sa.text(
                "ALTER TABLE engine_events DROP CONSTRAINT "
                "IF EXISTS uq_engine_events_aggregate_version"
            )
        )
        op.create_unique_constraint(
            "uq_engine_events_aggregate_version",
            "engine_events",
            ["aggregate_type", "aggregate_id", "aggregate_version"],
        )
    else:
        with op.batch_alter_table("engine_events") as batch:
            batch.drop_constraint(
                "uq_engine_events_aggregate_version", type_="unique"
            )
            batch.create_unique_constraint(
                "uq_engine_events_aggregate_version",
                ["aggregate_type", "aggregate_id", "aggregate_version"],
            )
