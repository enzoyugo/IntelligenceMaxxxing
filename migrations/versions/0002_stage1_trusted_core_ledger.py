"""Stage 1: identity, scoped ledger, integrity chain, projections, append-only SQL.

Revision ID: 0002_stage1
Revises: 0001_stage0
Create Date: 2026-07-19

Does NOT alter the hash of 0001_stage0. Destructive downgrade of this revision
is blocked by MigrationSafetyPolicy unless all Stage 1 safety flags are set.
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_stage1"
down_revision = "0001_stage0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        _upgrade_engine_events_postgres()
    else:
        _upgrade_engine_events_sqlite()

    op.create_index("ix_engine_events_owner_id", "engine_events", ["owner_id"])
    op.create_index("ix_engine_events_application_id", "engine_events", ["application_id"])
    op.create_index("ix_engine_events_event_hash", "engine_events", ["event_hash"])
    op.create_index(
        "ix_engine_events_stream",
        "engine_events",
        ["owner_id", "application_id", "global_position"],
    )

    # ---- audit_records: isolation columns ---------------------------------
    with op.batch_alter_table("audit_records") as batch:
        batch.add_column(sa.Column("tenant_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("owner_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("application_id", sa.String(length=64), nullable=True))
    op.execute(
        sa.text(
            "UPDATE audit_records SET "
            "tenant_id = 'tnt_legacy', "
            "owner_id = 'usr_legacy', "
            "application_id = 'app_legacy' "
            "WHERE tenant_id IS NULL"
        )
    )
    with op.batch_alter_table("audit_records") as batch:
        batch.alter_column("tenant_id", existing_type=sa.String(length=64), nullable=False)
        batch.alter_column("owner_id", existing_type=sa.String(length=64), nullable=False)
        batch.alter_column(
            "application_id", existing_type=sa.String(length=64), nullable=False
        )
    op.create_index("ix_audit_records_owner_id", "audit_records", ["owner_id"])
    op.create_index("ix_audit_records_application_id", "audit_records", ["application_id"])

    # ---- idempotency_keys: composite scope --------------------------------
    op.drop_table("idempotency_keys")
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("application_id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("observation_id", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("audit_id", sa.String(length=64), nullable=False),
        sa.UniqueConstraint(
            "application_id",
            "owner_id",
            "action",
            "idempotency_key",
            name="uq_idempotency_scope_key",
        ),
    )

    # ---- identity tables --------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("audit_id", sa.String(length=64), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("audit_id", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    op.create_table(
        "applications",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("audit_id", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_applications_tenant_id", "applications", ["tenant_id"])
    op.create_index("ix_applications_owner_id", "applications", ["owner_id"])

    op.create_table(
        "application_credentials",
        sa.Column("credential_id", sa.String(length=64), primary_key=True),
        sa.Column("application_id", sa.String(length=64), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audit_id", sa.String(length=64), nullable=False),
    )
    op.create_index(
        "ix_application_credentials_application_id",
        "application_credentials",
        ["application_id"],
    )

    # ---- projections (derived, rebuildable) -------------------------------
    op.create_table(
        "accepted_observations",
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
        "ix_accepted_observations_global_position",
        "accepted_observations",
        ["global_position"],
    )
    op.create_index("ix_accepted_observations_owner_id", "accepted_observations", ["owner_id"])
    op.create_index(
        "ix_accepted_observations_application_id",
        "accepted_observations",
        ["application_id"],
    )
    op.create_index(
        "ix_accepted_observations_domain_pack", "accepted_observations", ["domain_pack"]
    )

    op.create_table(
        "projection_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("projection_name", sa.String(length=128), nullable=False),
        sa.Column("projection_version", sa.String(length=16), nullable=False),
        sa.Column("owner_scope", sa.String(length=64), nullable=False),
        sa.Column("application_scope", sa.String(length=64), nullable=False),
        sa.Column("last_global_position", sa.BigInteger(), nullable=False),
        sa.Column("last_event_id", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.UniqueConstraint(
            "projection_name",
            "projection_version",
            "owner_scope",
            "application_scope",
            name="uq_projection_checkpoint_scope",
        ),
    )

    if is_postgres:
        _install_append_only_protections()
        _install_roles_and_grants()


def _upgrade_engine_events_postgres() -> None:
    op.add_column("engine_events", sa.Column("global_position", sa.BigInteger(), nullable=True))
    op.add_column("engine_events", sa.Column("tenant_id", sa.String(length=64), nullable=True))
    op.add_column("engine_events", sa.Column("owner_id", sa.String(length=64), nullable=True))
    op.add_column(
        "engine_events", sa.Column("application_id", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "engine_events", sa.Column("previous_event_hash", sa.String(length=64), nullable=True)
    )
    op.add_column("engine_events", sa.Column("event_hash", sa.String(length=64), nullable=True))

    op.execute(
        sa.text(
            "UPDATE engine_events SET "
            "tenant_id = 'tnt_legacy', "
            "owner_id = 'usr_legacy', "
            "application_id = 'app_legacy' "
            "WHERE tenant_id IS NULL"
        )
    )
    op.execute(
        sa.text(
            "CREATE SEQUENCE IF NOT EXISTS engine_events_global_position_seq "
            "OWNED BY engine_events.global_position"
        )
    )
    op.execute(
        sa.text(
            "UPDATE engine_events SET global_position = nextval("
            "'engine_events_global_position_seq') "
            "WHERE global_position IS NULL"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE engine_events "
            "ALTER COLUMN global_position SET DEFAULT "
            "nextval('engine_events_global_position_seq')"
        )
    )
    op.execute(sa.text("ALTER TABLE engine_events DROP CONSTRAINT engine_events_pkey"))
    op.execute(sa.text("ALTER TABLE engine_events ADD PRIMARY KEY (global_position)"))
    op.execute(
        sa.text(
            "ALTER TABLE engine_events "
            "ADD CONSTRAINT uq_engine_events_event_id UNIQUE (event_id)"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE engine_events DROP CONSTRAINT "
            "IF EXISTS uq_engine_events_idempotency_scope_key"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE engine_events ADD CONSTRAINT "
            "uq_engine_events_idempotency_scope_key "
            "UNIQUE (application_id, idempotency_scope, idempotency_key)"
        )
    )
    op.execute(sa.text("ALTER TABLE engine_events ALTER COLUMN tenant_id SET NOT NULL"))
    op.execute(sa.text("ALTER TABLE engine_events ALTER COLUMN owner_id SET NOT NULL"))
    op.execute(sa.text("ALTER TABLE engine_events ALTER COLUMN application_id SET NOT NULL"))
    op.execute(sa.text("ALTER TABLE engine_events ALTER COLUMN global_position SET NOT NULL"))


def _upgrade_engine_events_sqlite() -> None:
    """Rebuild engine_events for SQLite (used by hermetic migration tests)."""
    op.rename_table("engine_events", "engine_events_old")
    op.create_table(
        "engine_events",
        sa.Column("global_position", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("aggregate_type", sa.String(length=128), nullable=False),
        sa.Column("aggregate_id", sa.String(length=64), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("domain_pack", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("application_id", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("audit_id", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_scope", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=256), nullable=True),
        sa.Column("previous_event_hash", sa.String(length=64), nullable=True),
        sa.Column("event_hash", sa.String(length=64), nullable=True),
        sa.UniqueConstraint("event_id", name="uq_engine_events_event_id"),
        sa.UniqueConstraint(
            "application_id",
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
    op.execute(
        sa.text(
            """
            INSERT INTO engine_events (
                event_id, event_type, schema_version, aggregate_type, aggregate_id,
                aggregate_version, domain_pack, tenant_id, owner_id, application_id,
                actor_type, actor_id, payload, occurred_at, recorded_at, audit_id,
                request_id, idempotency_scope, idempotency_key,
                previous_event_hash, event_hash
            )
            SELECT
                event_id, event_type, schema_version, aggregate_type, aggregate_id,
                aggregate_version, domain_pack,
                'tnt_legacy', 'usr_legacy', 'app_legacy',
                actor_type, actor_id, payload, occurred_at, recorded_at, audit_id,
                request_id, idempotency_scope, idempotency_key,
                NULL, NULL
            FROM engine_events_old
            """
        )
    )
    op.drop_table("engine_events_old")
    # Recreate the Stage 0 indexes that rename_table moved away.
    op.create_index("ix_engine_events_event_type", "engine_events", ["event_type"])
    op.create_index("ix_engine_events_aggregate_id", "engine_events", ["aggregate_id"])
    op.create_index("ix_engine_events_audit_id", "engine_events", ["audit_id"])


def _install_append_only_protections() -> None:
    """Defensive triggers: reject UPDATE/DELETE/TRUNCATE on ledger tables.

    projection_checkpoints: DELETE/TRUNCATE rejected; UPDATE is allowed
    (documented exception: derived state). Governance events live in
    engine_events - there is no separate governance_events table.
    """
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION engine_reject_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION
                    'append-only violation: % on % is forbidden',
                    TG_OP, TG_TABLE_NAME
                    USING ERRCODE = 'integrity_constraint_violation';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
    for table in ("engine_events", "audit_records"):
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER trg_{table}_forbid_update
                BEFORE UPDATE ON {table}
                FOR EACH ROW EXECUTE FUNCTION engine_reject_mutation();
                """
            )
        )
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

    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_projection_checkpoints_forbid_delete
            BEFORE DELETE ON projection_checkpoints
            FOR EACH ROW EXECUTE FUNCTION engine_reject_mutation();
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_projection_checkpoints_forbid_truncate
            BEFORE TRUNCATE ON projection_checkpoints
            FOR EACH STATEMENT EXECUTE FUNCTION engine_reject_mutation();
            """
        )
    )


def _install_roles_and_grants() -> None:
    """Create engine_migrator / engine_runtime / engine_readonly with least privilege.

    Passwords are NOT set here. Operators set them out of band (see
    docs/runbooks/POSTGRESQL_SETUP.md). Roles are created IF NOT EXISTS so
    re-running the migration on a prepared database is idempotent.
    """
    for role in ("engine_migrator", "engine_runtime", "engine_readonly"):
        op.execute(
            sa.text(
                f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN
                        CREATE ROLE {role} NOINHERIT LOGIN;
                    END IF;
                END
                $$;
                """
            )
        )

    # Schema usage
    op.execute(sa.text("GRANT USAGE ON SCHEMA public TO engine_runtime, engine_readonly"))
    op.execute(sa.text("GRANT ALL ON SCHEMA public TO engine_migrator"))

    # Ledger: runtime may SELECT + INSERT only
    for table in ("engine_events", "audit_records"):
        op.execute(sa.text(f"GRANT SELECT, INSERT ON {table} TO engine_runtime"))
        op.execute(sa.text(f"GRANT SELECT ON {table} TO engine_readonly"))
        op.execute(
            sa.text(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM engine_runtime")
        )
        op.execute(
            sa.text(
                f"REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON {table} FROM engine_readonly"
            )
        )

    # Sequence for global_position
    op.execute(
        sa.text(
            "GRANT USAGE, SELECT ON SEQUENCE engine_events_global_position_seq "
            "TO engine_runtime"
        )
    )

    # Idempotency + identity: runtime needs full DML for its own tables
    for table in (
        "idempotency_keys",
        "tenants",
        "users",
        "applications",
        "application_credentials",
    ):
        op.execute(
            sa.text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO engine_runtime")
        )
        op.execute(sa.text(f"GRANT SELECT ON {table} TO engine_readonly"))

    # Projections: derived state - runtime may mutate; readonly may only read
    op.execute(
        sa.text(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON accepted_observations TO engine_runtime"
        )
    )
    op.execute(sa.text("GRANT SELECT ON accepted_observations TO engine_readonly"))
    # Checkpoints: UPDATE allowed (derived); DELETE/TRUNCATE revoked for runtime
    # (triggers also reject DELETE/TRUNCATE). Rebuilds UPDATE the single row.
    op.execute(
        sa.text(
            "GRANT SELECT, INSERT, UPDATE ON projection_checkpoints TO engine_runtime"
        )
    )
    op.execute(sa.text("REVOKE DELETE, TRUNCATE ON projection_checkpoints FROM engine_runtime"))
    op.execute(sa.text("GRANT SELECT ON projection_checkpoints TO engine_readonly"))

    # Sequences for tables with serial PKs
    for seq in (
        "idempotency_keys_id_seq",
        "projection_checkpoints_id_seq",
    ):
        op.execute(
            sa.text(
                f"""
                DO $$
                BEGIN
                    IF EXISTS (SELECT FROM pg_class WHERE relname = '{seq}') THEN
                        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE {seq} TO engine_runtime';
                    END IF;
                END
                $$;
                """
            )
        )


def downgrade() -> None:
    """Destructive: drops Stage 1 structures. Blocked by MigrationSafetyPolicy
    unless all safety flags, backup ID and ADMINISTER_ENGINE are present.
    """
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        for table in ("engine_events", "audit_records", "projection_checkpoints"):
            for op_name in ("update", "delete", "truncate"):
                op.execute(
                    sa.text(f"DROP TRIGGER IF EXISTS trg_{table}_forbid_{op_name} ON {table}")
                )
        op.execute(sa.text("DROP FUNCTION IF EXISTS engine_reject_mutation()"))

    for table in (
        "projection_checkpoints",
        "accepted_observations",
        "application_credentials",
        "applications",
        "users",
        "tenants",
        "idempotency_keys",
    ):
        op.drop_table(table)

    # Recreate Stage 0 idempotency_keys shape so downgrade lands on 0001 schema.
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

    # Note: restoring engine_events / audit_records to the exact Stage 0 PK
    # shape is intentionally incomplete (global_position columns remain). A
    # real destructive rollback of history is an extraordinary maintenance
    # operation documented in MIGRATION_SAFETY.md, not a casual alembic
    # downgrade. The safety policy exists to keep this path gated.
