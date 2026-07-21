# Isolated wellbeing scale + isolation smoke.
# Creates a TEMPORARY PostgreSQL database, migrates to head, starts Engine on a
# non-production port, runs SDK submits with TEST provenance, then tears down.
#
# Never targets the personal production ledger.
param(
    [switch]$Isolated,
    [switch]$KeepArtifacts,
    [switch]$AllowProductionAudit,
    [string]$EngineRoot = ""
)

$ErrorActionPreference = "Stop"
if (-not $PSBoundParameters.ContainsKey("Isolated")) { $Isolated = $true }

function Fail($Message) {
    Write-Host "ISOLATION_SMOKE FAILED: $Message" -ForegroundColor Red
    Cleanup
    exit 1
}

$script:engineProc = $null
$script:dbName = $null
$script:artifactDir = $null

function Cleanup {
    if ($script:engineProc -and -not $script:engineProc.HasExited) {
        Stop-Process -Id $script:engineProc.Id -Force -ErrorAction SilentlyContinue
    }
    if ($script:dbName -and -not $KeepArtifacts) {
        try {
            docker compose exec -T postgres psql -U intelligence -d postgres `
                -c "DROP DATABASE IF EXISTS $($script:dbName) WITH (FORCE)" | Out-Null
        } catch { }
    }
}

if (-not $EngineRoot) {
    $EngineRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
Set-Location $EngineRoot

if (-not $Isolated) {
    Fail "Non-isolated mode removed. Use -Isolated (default). Refusing personal ledger writes."
}

$enginePort = 8117
if ($enginePort -eq 8100 -and -not $AllowProductionAudit) {
    Fail "refusing production Engine port 8100"
}

$ready = docker compose exec -T postgres pg_isready 2>&1
if ($LASTEXITCODE -ne 0 -or ("$ready" -notmatch "accepting connections")) {
    docker compose up -d
    Start-Sleep -Seconds 4
    $ready = docker compose exec -T postgres pg_isready 2>&1
    if ($LASTEXITCODE -ne 0 -or ("$ready" -notmatch "accepting connections")) {
        Fail "postgres not available — isolated smoke requires Docker PostgreSQL (no personal DB fallback)"
    }
}

$script:dbName = "intelligence_maxxxing_iso_smoke_$(Get-Date -Format 'yyyyMMddHHmmss')"
if ($script:dbName -notmatch "iso_smoke") {
    Fail "refusing non-isolated database name"
}

docker compose exec -T postgres psql -U intelligence -d postgres `
    -c "DROP DATABASE IF EXISTS $($script:dbName) WITH (FORCE)" | Out-Null
docker compose exec -T postgres psql -U intelligence -d postgres `
    -c "CREATE DATABASE $($script:dbName)" | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "could not create temp database" }

$env:DATABASE_URL = "postgresql+psycopg://intelligence:intelligence@127.0.0.1:5432/$($script:dbName)"
if ($env:DATABASE_URL -match "/intelligence_maxxxing$" -and -not $AllowProductionAudit) {
    Fail "refusing production DATABASE_URL"
}

python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Fail "alembic upgrade head failed" }

$boot = python -m intelligence_maxxxing.cli bootstrap-owner --tenant-name "ISO Smoke Tenant" --owner-name "ISO Smoke Owner"
if ($LASTEXITCODE -ne 0) { Fail "bootstrap-owner failed" }
$ownerId = ($boot | Select-String "owner_id=(.+)").Matches[0].Groups[1].Value
$reg = python -m intelligence_maxxxing.cli register-application --display-name "ISO-Smoke-App" --owner-id $ownerId
$appId = ($reg | Select-String "application_id=(.+)").Matches[0].Groups[1].Value
foreach ($s in "SUBMIT_OBSERVATION", "READ_AUDIT", "READ_INTELLIGENCE") {
    python -m intelligence_maxxxing.cli grant-scope --application-id $appId --scope $s | Out-Null
}
$cred = python -m intelligence_maxxxing.cli create-credential --application-id $appId
$secret = ($cred | Select-String "secret=(.+)").Matches[0].Groups[1].Value

$script:engineProc = Start-Process -PassThru -WindowStyle Hidden -FilePath "python" `
    -WorkingDirectory $EngineRoot `
    -ArgumentList "-m", "uvicorn", "--factory", "intelligence_maxxxing.api.app:create_app", "--host", "127.0.0.1", "--port", "$enginePort"

$deadline = (Get-Date).AddSeconds(45)
$healthy = $false
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$enginePort/health/live" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $healthy = $true; break }
    } catch { Start-Sleep -Milliseconds 400 }
}
if (-not $healthy) { Fail "Engine did not become healthy on port $enginePort" }

$script:artifactDir = Join-Path $EngineRoot "artifacts\isolation_smoke\$($script:dbName)"
New-Item -ItemType Directory -Force -Path $script:artifactDir | Out-Null

$env:ISO_ENGINE_URL = "http://127.0.0.1:$enginePort"
$env:ISO_ENGINE_SECRET = $secret
$env:ISO_ARTIFACT_DIR = $script:artifactDir

python scripts/smoke/wellbeing_isolation_canary.py
if ($LASTEXITCODE -ne 0) { Fail "isolation canary failed" }

Write-Host "ISOLATION_SMOKE PASS db=$($script:dbName) port=$enginePort artifacts=$($script:artifactDir)"
if (-not $KeepArtifacts) {
    Cleanup
    Write-Host "Temporary database destroyed."
} else {
    if ($script:engineProc -and -not $script:engineProc.HasExited) {
        Stop-Process -Id $script:engineProc.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "KeepArtifacts: database $($script:dbName) retained; Engine stopped."
}
exit 0
