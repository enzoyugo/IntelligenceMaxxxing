# PostgreSQL Append-Only Enforcement — Stage 1

**Status:** IMPLEMENTED (Stage 1, PostgreSQL only)  
**Authority:** Constitution Art. 34, Technical Architecture §8  
**Code:** `migrations/versions/0002_stage1_trusted_core_ledger.py`

---

## 1. Purpose

Stage 1 adds database-level defenses so the ledger cannot be silently mutated, even if application code regresses. Protections apply on **PostgreSQL** (production/development). SQLite (tests only) relies on application-layer guards.

---

## 2. Protected tables

### engine_events — strict append-only

| Operation | Allowed |
|---|---|
| SELECT | Yes (runtime + readonly roles) |
| INSERT | Yes (runtime role) |
| UPDATE | **Blocked** (REVOKE + trigger) |
| DELETE | **Blocked** (REVOKE + trigger) |
| TRUNCATE | **Blocked** (REVOKE + trigger) |

Primary key changed to `global_position` (bigserial sequence). `event_id` remains unique.

Stage 1 adds isolation columns: `tenant_id`, `owner_id`, `application_id`, `previous_event_hash`, `event_hash`.

### audit_records — strict append-only

Same REVOKE + trigger protections as `engine_events`.

Stage 1 adds `tenant_id`, `owner_id`, `application_id` columns (backfilled for legacy rows).

### projection_checkpoints — derived mutable state

| Operation | Allowed |
|---|---|
| SELECT | Yes |
| INSERT | Yes (runtime) |
| UPDATE | **Yes** (documented append-only exception) |
| DELETE | **Blocked** (trigger) |
| TRUNCATE | **Blocked** (trigger) |

Checkpoints are disposable derived bookkeeping. Rebuilds UPDATE the single row per projection scope.

### accepted_observations — derived, fully mutable

Runtime role has SELECT, INSERT, UPDATE, DELETE (rebuilds wipe and repopulate). This table is not part of the immutable ledger.

### event_stream_heads / integrity_checkpoints — derived control state (Stage 1.1)

Added by migration `0003_stage1_1_integrity_isolation_hardening`.

| Operation | Allowed |
|---|---|
| SELECT | Yes |
| INSERT | Yes (runtime) |
| UPDATE | **Yes** (governed: append advances the head; verify advances the checkpoint; quarantine/release update status) |
| DELETE | **Blocked** (trigger) |
| TRUNCATE | **Blocked** (trigger) |

These are engine-managed control state, not ledger evidence. The runtime role may advance
them only through the governed append/verify/quarantine/release paths and can never clear a
quarantine arbitrarily. See `docs/architecture/STREAM_HEAD_AND_QUARANTINE_MODEL.md`.

### accepted_observations_shadow — staging, fully mutable (Stage 1.1)

Staging copy used for non-destructive verify and atomic rebuild-then-promote. Runtime role
has full DML; it holds no historical truth. See `docs/architecture/PROJECTION_MODEL.md §3.1`.

---

## 3. Trigger implementation

Function: `engine_reject_mutation()`

Raises `integrity_constraint_violation` on forbidden operations with message: `append-only violation: <OP> on <TABLE> is forbidden`.

Triggers installed per table:

| Table | UPDATE | DELETE | TRUNCATE |
|---|---|---|---|
| `engine_events` | blocked | blocked | blocked |
| `audit_records` | blocked | blocked | blocked |
| `projection_checkpoints` | allowed | blocked | blocked |
| `event_stream_heads` (Stage 1.1) | allowed | blocked | blocked |
| `integrity_checkpoints` (Stage 1.1) | allowed | blocked | blocked |

---

## 4. Governance events storage

Identity, permission, projection, and integrity events live in **`engine_events`**. There is **no** separate `governance_events` table. Append-only protections cover governance history equally.

---

## 5. Database roles

Migration `0002_stage1` creates three least-privilege roles (passwords set **out of band**, never in migration code):

| Role | Purpose | Grants |
|---|---|---|
| `engine_migrator` | Alembic migrations | ALL on schema public |
| `engine_runtime` | Engine process | INSERT+SELECT on ledger; full DML on identity/idempotency; INSERT/UPDATE/DELETE on projections; INSERT/UPDATE on checkpoints |
| `engine_readonly` | Reporting / diagnostics | SELECT only on all tables |

Explicit REVOKEs:

- `engine_runtime`: no UPDATE/DELETE/TRUNCATE on `engine_events` or `audit_records`; no DELETE/TRUNCATE on `projection_checkpoints`
- `engine_readonly`: no INSERT/UPDATE/DELETE/TRUNCATE on ledger tables

Sequence grant: `engine_events_global_position_seq` → USAGE, SELECT for `engine_runtime`.

See `docs/runbooks/POSTGRESQL_SETUP.md` for operator setup.

---

## 6. Application-layer guards (all databases)

Even without PostgreSQL triggers, the codebase enforces append-only at the port level:

- `EventStorePort` / `AuditStorePort` expose append + read only (no update/delete methods)
- Constitutional tests: `EVENT_STORE_EXPOSES_NO_UPDATE`, `EVENT_STORE_EXPOSES_NO_DELETE`, `EVENTS_ARE_APPEND_ONLY`

SQLite test databases do not install triggers; these tests provide the guard.

---

## 7. Extraordinary maintenance procedure

Normal Alembic downgrade of `0002_stage1` is **destructive** and blocked by `MigrationSafetyPolicy` (see `docs/runbooks/MIGRATION_SAFETY.md`).

If extraordinary maintenance is truly required (e.g. forensic recovery on a compromised ledger):

1. Set all migration safety flags and confirm phrase
2. Take and verify a backup; record `ENGINE_CONFIRMED_BACKUP_ID`
3. Put the Engine in maintenance mode
4. Connect as superuser or `engine_migrator` (not `engine_runtime`)
5. Drop triggers explicitly if direct table surgery is needed
6. Perform the maintenance under audit
7. Re-run migrations forward; verify integrity chain and projections
8. Document the incident

Casual `alembic downgrade` is not a supported operator workflow.

---

## 8. Explicitly not in Stage 1

- Row-level security policies
- Encryption at rest
- Read replicas or streaming replication setup
- Automated backup verification (backup ID is a manual gate only)
- Trigger enforcement on SQLite
