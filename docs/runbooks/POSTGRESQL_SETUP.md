# PostgreSQL Setup — Stage 1

**Audience:** Operators setting up the local Engine backend  
**Prerequisites:** Docker Desktop (or an existing PostgreSQL 16 instance)

---

## 1. Start PostgreSQL

From the repository root:

```powershell
docker compose up -d postgres
```

Or use the helper script (waits for health check):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\start_postgres.ps1
```

### Container specification

| Setting | Value |
|---|---|
| Image | `postgres:16-alpine` |
| Container name | `intelligence_maxxxing_postgres` |
| Bind address | `127.0.0.1:5432` (localhost only) |
| Database | `intelligence_maxxxing` |
| Default superuser | `intelligence` (dev compose only) |

The compose file is `docker-compose.yml`. Data persists in the `intelligence_maxxxing_pgdata` Docker volume.

---

## 2. Configure connection

Copy `.env.example` to `.env` and set `DATABASE_URL`. Example (credentials redacted):

```text
DATABASE_URL=postgresql+psycopg://<user>:<password>@127.0.0.1:5432/intelligence_maxxxing
```

Never commit real passwords. The dev compose defaults (`intelligence`/`intelligence`) are for local development only.

---

## 3. Apply migrations

```powershell
powershell -ExecutionPolicy Bypass -File scripts\db\upgrade.ps1
```

Or directly:

```powershell
python -m alembic upgrade head
```

Stage 1 migration `0002_stage1` adds identity tables, projection tables, integrity columns, append-only triggers (PostgreSQL), and database roles.

---

## 4. Database roles (migration 0002)

Migration `0002_stage1` creates three roles **without passwords**:

| Role | Use |
|---|---|
| `engine_migrator` | Alembic upgrades/downgrades |
| `engine_runtime` | Engine API and CLI at runtime |
| `engine_readonly` | Read-only diagnostics |

**Passwords must be set out of band** after migration. Example (run as PostgreSQL superuser):

```sql
ALTER ROLE engine_migrator PASSWORD '<strong-password>';
ALTER ROLE engine_runtime PASSWORD '<strong-password>';
ALTER ROLE engine_readonly PASSWORD '<strong-password>';
```

Then point `DATABASE_URL` at the appropriate role:

```text
DATABASE_URL=postgresql+psycopg://engine_runtime:<password>@127.0.0.1:5432/intelligence_maxxxing
```

Passwords are never hardcoded in migrations, scripts, or documentation.

---

## 5. Verify

```powershell
# Readiness (no auth)
curl.exe http://127.0.0.1:8100/health/ready

# After bootstrap + credential (see CREDENTIAL_BOOTSTRAP.md)
curl.exe http://127.0.0.1:8100/api/v1/health -H "Authorization: Bearer <secret>"
```

Quality gates include migration safety and append-only tests:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\audit\run_quality_gates.ps1
```

---

## 6. Stop PostgreSQL

```powershell
docker compose stop postgres
```

To remove data (destructive):

```powershell
docker compose down -v
```

---

## 7. SQLite (tests only)

Pytest uses in-memory or file SQLite databases. Append-only SQL triggers are **not** installed on SQLite. Do not point production `DATABASE_URL` at SQLite.

---

## 8. Troubleshooting

| Symptom | Check |
|---|---|
| `connection refused` on 5432 | `docker compose ps`; wait for health check |
| `role "engine_runtime" does not exist` | Run `alembic upgrade head` |
| `append-only violation` on UPDATE | Expected — ledger tables are immutable |
| Migration fails mid-way | Fix cause, restore from backup if needed; do not partial-upgrade production |

See also: `docs/architecture/POSTGRES_APPEND_ONLY_ENFORCEMENT.md`, `docs/runbooks/MIGRATION_SAFETY.md`.
