# RUNBOOK — LOCAL DEVELOPMENT (Windows)

## Prerequisites

- Python 3.12+
- Git
- Docker Desktop (only needed for local PostgreSQL; tests do not need it)

## First-time setup

```powershell
cd E:\IntelligenceMaxxxing
powershell -ExecutionPolicy Bypass -File scripts\dev\setup_engine.ps1
```

## Start PostgreSQL (requires Docker)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\start_postgres.ps1
```

## Apply migrations

```powershell
powershell -ExecutionPolicy Bypass -File scripts\db\upgrade.ps1
```

## Run the Engine

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\run_engine.ps1
# Health: http://127.0.0.1:8100/api/v1/health
```

## Stop the Engine

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\stop_engine.ps1
```

## Run all quality gates

```powershell
powershell -ExecutionPolicy Bypass -File scripts\audit\run_quality_gates.ps1
```

## Verify the constitutional manifest only

```powershell
powershell -ExecutionPolicy Bypass -File scripts\audit\verify_constitution.ps1
```

## Run tests directly

```powershell
python -m pytest -q                       # everything (no external services needed)
python -m pytest tests/constitutional -q  # constitutional suite only
```

## Troubleshooting

- **Health shows `database: UNHEALTHY`:** PostgreSQL is not running or
  `DATABASE_URL` in `.env` is wrong. The Engine does not hide this; fix the
  database, don't fake the health.
- **`docker` not found:** install Docker Desktop or point `DATABASE_URL` at an
  existing PostgreSQL instance.
- **Manifest verification fails:** a constitutional document changed. If the
  change was legitimate and approved, regenerate the manifest and record the
  amendment in `CONSTITUTIONAL_CHANGES.md`. Otherwise restore the document.
