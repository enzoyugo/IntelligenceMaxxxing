# Migration Safety — Stage 1

**Audience:** Operators considering destructive database migrations  
**Code:** `application/use_cases/integrity.py` (`MigrationSafetyPolicy`), `config/settings.py`

---

## 1. Purpose

Destructive Alembic downgrades — especially `0002_stage1` — can drop identity tables, projections, and append-only protections. Stage 1 blocks these operations by default through `MigrationSafetyPolicy`.

Casual `alembic downgrade` is not a supported operator workflow.

---

## 2. MigrationSafetyPolicy

All of the following must be true for a destructive downgrade to proceed:

| Requirement | Environment variable / condition |
|---|---|
| Destructive migrations explicitly allowed | `ENGINE_DESTRUCTIVE_MIGRATIONS_ALLOWED=true` |
| Engine in maintenance mode | `ENGINE_MAINTENANCE_MODE=true` |
| Verified backup recorded | `ENGINE_CONFIRMED_BACKUP_ID=<non-empty backup id>` |
| Actor holds admin scope | `ADMINISTER_ENGINE` (CLI/policy context) |
| Confirm phrase | Exact match: `I UNDERSTAND THIS DESTROYS HISTORY` |

If any requirement fails, `MigrationSafetyPolicy.authorize()` returns blocking reasons and the downgrade must not proceed.

Defaults (safe):

```text
ENGINE_DESTRUCTIVE_MIGRATIONS_ALLOWED=false
ENGINE_MAINTENANCE_MODE=false
ENGINE_CONFIRMED_BACKUP_ID=(unset)
```

---

## 3. Protected tests

| Test | Asserts |
|---|---|
| `DESTRUCTIVE_DOWNGRADE_BLOCKED_BY_DEFAULT` | Empty request → blockers present |
| `DESTRUCTIVE_DOWNGRADE_REQUIRES_BACKUP_ID` | Missing backup id → blocked |
| `DESTRUCTIVE_DOWNGRADE_REQUIRES_ADMIN` | Missing `ADMINISTER_ENGINE` → blocked |

(`tests/unit/test_migration_safety.py`)

---

## 4. Safe upgrade (normal operation)

Upgrades are always safe and ungated:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\db\upgrade.ps1
```

Or:

```powershell
python -m alembic upgrade head
```

---

## 5. Destructive downgrade (extraordinary)

Only when all policy gates pass:

```powershell
# Set environment (example)
$env:ENGINE_DESTRUCTIVE_MIGRATIONS_ALLOWED = "true"
$env:ENGINE_MAINTENANCE_MODE = "true"
$env:ENGINE_CONFIRMED_BACKUP_ID = "backup-verified-20260719-001"

# Use the safe wrapper (checks policy before invoking alembic)
powershell -ExecutionPolicy Bypass -File scripts\db\safe_downgrade.ps1 -Revision 0001_stage0 -ConfirmPhrase "I UNDERSTAND THIS DESTROYS HISTORY"
```

`scripts/db/safe_downgrade.ps1` evaluates `MigrationSafetyPolicy` before calling Alembic. It requires an operator with `ADMINISTER_ENGINE` scope granted via CLI.

**Warning:** Even an authorized downgrade of `0002_stage1` does not fully restore Stage 0 `engine_events` primary-key shape. A real destructive rollback of history is documented as extraordinary maintenance in `POSTGRES_APPEND_ONLY_ENFORCEMENT.md`.

---

## 6. Pre-downgrade checklist

- [ ] Full PostgreSQL backup taken and verified restorable
- [ ] Backup id recorded in `ENGINE_CONFIRMED_BACKUP_ID`
- [ ] Engine stopped (maintenance mode)
- [ ] All safety flags set
- [ ] Confirm phrase ready
- [ ] Stakeholder sign-off for history destruction
- [ ] Post-downgrade plan: integrity verify + projection rebuild if re-upgrading

---

## 7. What is NOT gated

- `alembic upgrade head` (forward migrations)
- Read-only queries
- Projection rebuilds
- Integrity verification
- Identity bootstrap CLI commands

---

## 8. Explicitly not in Stage 1

- Automated backup verification against `ENGINE_CONFIRMED_BACKUP_ID`
- HTTP endpoint for migration control
- Blue/green migration orchestration
- Online schema change without downtime

See also: `docs/runbooks/POSTGRESQL_SETUP.md`, `docs/architecture/POSTGRES_APPEND_ONLY_ENFORCEMENT.md`.
