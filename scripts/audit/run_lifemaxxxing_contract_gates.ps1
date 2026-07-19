# Stage 2 cross-repository contract gates: Engine <-> LifeMaxxxing.
#
# Proves, against REAL PostgreSQL and REAL HTTP servers:
#   * the standalone SDK wheel builds and certifies (no Engine Core),
#   * the LifeMaxxxing backend suite passes,
#   * online canaries: check-in + workout sync, replay idempotency, data
#     minimization (free text never reaches the Engine), audit recoverability
#     through the Life backend, typed errors, cross-application isolation,
#   * offline canaries: Life backend healthy + typed retryable errors when the
#     Engine is down,
#   * secret scan: no Engine credential in any tracked LifeMaxxxing file.
$ErrorActionPreference = "Stop"
$engineRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $engineRoot

$enginePort = 8110
$lifePort = 8011
$engineProc = $null
$lifeProc = $null

function Fail($Message) {
    Write-Host "LIFEMAXXXING CONTRACT GATE FAILED: $Message" -ForegroundColor Red
    Cleanup
    exit 1
}

function Cleanup {
    foreach ($p in @($script:engineProc, $script:lifeProc)) {
        if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    }
}

function Wait-Healthy($Url, $Name, $TimeoutSec = 40) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -eq 200) { return }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    Fail "$Name did not become healthy at $Url"
}

# --- 0. Resolve the LifeMaxxxing root -----------------------------------------
$candidates = @(
    $env:LIFEMAXXXING_ROOT,
    "C:\Users\AORUS\lifeos-maxxxing"
) | Where-Object { $_ }
$lifeRoot = $null
foreach ($c in $candidates) {
    if ((Test-Path (Join-Path $c "package.json")) -and (Test-Path (Join-Path $c "src\server\app.py"))) {
        $lifeRoot = $c; break
    }
}
if (-not $lifeRoot) { Fail "STAGE_2_BLOCKED_LIFEMAXXXING_ROOT_NOT_FOUND (set LIFEMAXXXING_ROOT)" }
Write-Host "LifeMaxxxing root: $lifeRoot"

# --- 1. Standalone SDK build + clean-venv certification -----------------------
Write-Host "==> Gate 1/6: standalone SDK build + certification..."
powershell -ExecutionPolicy Bypass -File scripts/sdk/build_client_sdk.ps1
if ($LASTEXITCODE -ne 0) { Fail "SDK build failed" }
powershell -ExecutionPolicy Bypass -File scripts/sdk/test_client_sdk.ps1
if ($LASTEXITCODE -ne 0) { Fail "SDK clean-venv certification failed" }

# --- 2. Real PostgreSQL, dedicated E2E database --------------------------------
Write-Host "==> Gate 2/6: PostgreSQL E2E database from zero..."
$ready = docker compose exec -T postgres pg_isready 2>&1
if ($LASTEXITCODE -ne 0 -or ($ready -notmatch "accepting connections")) {
    docker compose up -d
    Start-Sleep -Seconds 3
    $ready = docker compose exec -T postgres pg_isready 2>&1
    if ($LASTEXITCODE -ne 0 -or ($ready -notmatch "accepting connections")) {
        Fail "postgres is not accepting connections. No SQLite fallback."
    }
}
$dbName = "intelligence_maxxxing_stage2_e2e"
docker compose exec -T postgres psql -U intelligence -d postgres -c "DROP DATABASE IF EXISTS $dbName WITH (FORCE)" | Out-Null
docker compose exec -T postgres psql -U intelligence -d postgres -c "CREATE DATABASE $dbName" | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "could not recreate E2E database" }
$env:DATABASE_URL = "postgresql+psycopg://intelligence:intelligence@127.0.0.1:5432/$dbName"
python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Fail "alembic upgrade head failed on the E2E database" }

# --- 3. Register identities via the governed CLI ------------------------------
Write-Host "==> Gate 3/6: registering LifeMaxxxing + a second app (isolation control)..."
$boot = python -m intelligence_maxxxing.cli bootstrap-owner --tenant-name "E2E Tenant" --owner-name "E2E Owner"
if ($LASTEXITCODE -ne 0) { Fail "bootstrap-owner failed" }
$ownerId = ($boot | Select-String "owner_id=(.+)").Matches[0].Groups[1].Value

function New-AppCredential($DisplayName) {
    $reg = python -m intelligence_maxxxing.cli register-application --display-name $DisplayName --owner-id $ownerId
    if ($LASTEXITCODE -ne 0) { Fail "register-application $DisplayName failed" }
    $appId = ($reg | Select-String "application_id=(.+)").Matches[0].Groups[1].Value
    foreach ($s in "SUBMIT_OBSERVATION", "READ_AUDIT", "READ_INTELLIGENCE") {
        python -m intelligence_maxxxing.cli grant-scope --application-id $appId --scope $s | Out-Null
        if ($LASTEXITCODE -ne 0) { Fail "grant-scope $s failed" }
    }
    $cred = python -m intelligence_maxxxing.cli create-credential --application-id $appId
    if ($LASTEXITCODE -ne 0) { Fail "create-credential failed" }
    return ($cred | Select-String "secret=(.+)").Matches[0].Groups[1].Value
}
$lifeSecret = New-AppCredential "LifeMaxxxing-E2E"
$otherSecret = New-AppCredential "OtherApp-E2E"

# --- 4. LifeMaxxxing backend unit suite ----------------------------------------
Write-Host "==> Gate 4/6: LifeMaxxxing backend test suite..."
Push-Location $lifeRoot
$env:PYTHONPATH = "."
python -m unittest tests.test_intelligence
if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "LifeMaxxxing backend tests failed" }
Pop-Location

# --- 5. Live E2E: Engine + Life backend + canaries -----------------------------
Write-Host "==> Gate 5/6: online + offline canaries over real HTTP..."
$engineProc = Start-Process -PassThru -WindowStyle Hidden -FilePath "python" `
    -WorkingDirectory $engineRoot `
    -ArgumentList "-m", "uvicorn", "--factory", "intelligence_maxxxing.api.app:create_app", "--host", "127.0.0.1", "--port", "$enginePort"
Wait-Healthy "http://127.0.0.1:$enginePort/health/live" "Engine"

# Server-only Engine config is injected via process env (overrides .env.server).
$lifeEnv = @{
    PYTHONPATH = "."
    INTELLIGENCE_ENGINE_ENABLED = "true"
    INTELLIGENCE_ENGINE_BASE_URL = "http://127.0.0.1:$enginePort"
    INTELLIGENCE_ENGINE_CREDENTIAL = $lifeSecret
    BRAIN_ENABLED = "false"
}
$prevEnv = @{}
foreach ($k in $lifeEnv.Keys) {
    $prevEnv[$k] = [Environment]::GetEnvironmentVariable($k)
    [Environment]::SetEnvironmentVariable($k, $lifeEnv[$k])
}
$lifeProc = Start-Process -PassThru -WindowStyle Hidden -FilePath "python" `
    -WorkingDirectory $lifeRoot `
    -ArgumentList "-m", "uvicorn", "src.server.app:app", "--host", "127.0.0.1", "--port", "$lifePort"
foreach ($k in $prevEnv.Keys) { [Environment]::SetEnvironmentVariable($k, $prevEnv[$k]) }
Wait-Healthy "http://127.0.0.1:$lifePort/health" "LifeMaxxxing backend"

$env:E2E_ENGINE_URL = "http://127.0.0.1:$enginePort"
$env:E2E_LIFE_URL = "http://127.0.0.1:$lifePort"
$env:E2E_LIFE_CREDENTIAL = $lifeSecret
$env:E2E_OTHER_CREDENTIAL = $otherSecret

$env:E2E_PHASE = "online"
python scripts/audit/lifemaxxxing_e2e_canaries.py
if ($LASTEXITCODE -ne 0) { Fail "online canaries failed" }

Write-Host "==> Stopping the Engine to prove offline behaviour..."
Stop-Process -Id $engineProc.Id -Force
Start-Sleep -Seconds 1
$env:E2E_PHASE = "offline"
python scripts/audit/lifemaxxxing_e2e_canaries.py
if ($LASTEXITCODE -ne 0) { Fail "offline canaries failed" }

Stop-Process -Id $lifeProc.Id -Force -ErrorAction SilentlyContinue
$env:E2E_LIFE_CREDENTIAL = ""
$env:E2E_OTHER_CREDENTIAL = ""

# --- 6. Secret scan over LifeMaxxxing tracked files ----------------------------
Write-Host "==> Gate 6/6: secret scan (no credential in any tracked Life file)..."
Push-Location $lifeRoot
$ignored = git check-ignore .env.server 2>$null
if (-not $ignored) { Pop-Location; Fail ".env.server is NOT gitignored" }
$hits = git grep -I -l "imx_sk_" -- ":!tests/" ":!docs/" 2>$null
Pop-Location
if ($hits) { Fail "credential-like string found in tracked LifeMaxxxing files: $hits" }

Cleanup
Write-Host "ALL LIFEMAXXXING CONTRACT GATES PASSED" -ForegroundColor Green
exit 0
