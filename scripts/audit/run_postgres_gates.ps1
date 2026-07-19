# PostgreSQL Stage 1 gates. FAILS CLEARLY when PostgreSQL is unavailable.
# Never falls back to SQLite.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))

function Fail($Message) {
    Write-Host "POSTGRES GATE FAILED: $Message" -ForegroundColor Red
    exit 1
}

Write-Host "==> Checking Docker / postgres service..."
docker compose ps --status running 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "docker compose is not available or project failed" }

$ps = docker compose ps --format json 2>$null
if (-not $ps) {
    Write-Host "Starting postgres via docker compose..."
    docker compose up -d
    if ($LASTEXITCODE -ne 0) { Fail "could not start postgres container" }
}

$ready = docker compose exec -T postgres pg_isready 2>&1
if ($LASTEXITCODE -ne 0 -or ($ready -notmatch "accepting connections")) {
    Fail "postgres is not accepting connections (pg_isready failed). No SQLite fallback."
}
Write-Host "GATE PASSED: postgres accepting connections"

# Dedicated test database so gates never touch a long-lived human DB casually.
$env:DATABASE_URL = "postgresql+psycopg://intelligence:intelligence@127.0.0.1:5432/intelligence_maxxxing_stage1_gates"

Write-Host "==> Dropping and recreating gate database from zero..."
docker compose exec -T postgres psql -U intelligence -d postgres -c "DROP DATABASE IF EXISTS intelligence_maxxxing_stage1_gates WITH (FORCE)" | Out-Null
docker compose exec -T postgres psql -U intelligence -d postgres -c "CREATE DATABASE intelligence_maxxxing_stage1_gates"
if ($LASTEXITCODE -ne 0) { Fail "could not recreate gate database" }

Write-Host "==> Alembic upgrade head on real PostgreSQL..."
python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Fail "alembic upgrade head failed against PostgreSQL" }
Write-Host "GATE PASSED: alembic upgrade head"

Write-Host "==> Running PostgreSQL test suite..."
$env:ENGINE_RUN_POSTGRES_GATES = "1"
python -m pytest -q tests/postgres -m postgres
if ($LASTEXITCODE -ne 0) { Fail "PostgreSQL test suite failed" }
Write-Host "GATE PASSED: postgres tests"

# --- Stage 1.1 hardening gates: real multi-session concurrency, no SQLite ----
# These MUST run against real PostgreSQL. They measure:
#   * 20 concurrent distinct events on the SAME stream form ONE valid chain
#   * 20 concurrent events on DISTINCT streams do not block globally
#   * atomic stream-head updates / failed appends do not advance the head
#   * quarantine rejects appends
#   * full + incremental integrity agree
#   * non-destructive shadow projection verify
Write-Host "==> Running Stage 1.1 multi-session concurrency + integrity gates..."
python -m pytest -v tests/postgres/test_stage1_1_hardening.py -m postgres
if ($LASTEXITCODE -ne 0) { Fail "Stage 1.1 concurrency / integrity gates failed on real PostgreSQL" }
Write-Host "GATE PASSED: Stage 1.1 hardening (20 concurrent same-stream chain, distinct streams, quarantine, full/incremental integrity, shadow verify)"

Write-Host "ALL POSTGRES QUALITY GATES PASSED" -ForegroundColor Green
exit 0
