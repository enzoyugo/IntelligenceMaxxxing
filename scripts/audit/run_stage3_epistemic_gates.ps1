# Stage 3 first epistemic loop gates: Engine + LifeMaxxxing over real PostgreSQL/HTTP.
$ErrorActionPreference = "Stop"
$engineRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $engineRoot

$enginePort = 8120
$lifePort = 8021
$engineProc = $null
$lifeProc = $null

function Fail($Message) {
    Write-Host "STAGE 3 EPISTEMIC GATE FAILED: $Message" -ForegroundColor Red
    Cleanup
    exit 1
}

function Cleanup {
    foreach ($p in @($script:engineProc, $script:lifeProc)) {
        if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    }
}

function Wait-Healthy($Url, $Name, $TimeoutSec = 50) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -eq 200) { return }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    Fail "$Name did not become healthy at $Url"
}

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
if (-not $lifeRoot) { Fail "LIFEMAXXXING_ROOT not found" }
Write-Host "LifeMaxxxing root: $lifeRoot"

Write-Host "==> Gate 1/7: Engine quality gates..."
powershell -ExecutionPolicy Bypass -File scripts/audit/run_quality_gates.ps1
if ($LASTEXITCODE -ne 0) { Fail "Engine quality gates failed" }

Write-Host "==> Gate 2/7: standalone SDK build + certification..."
powershell -ExecutionPolicy Bypass -File scripts/sdk/build_client_sdk.ps1
if ($LASTEXITCODE -ne 0) { Fail "SDK build failed" }
powershell -ExecutionPolicy Bypass -File scripts/sdk/test_client_sdk.ps1
if ($LASTEXITCODE -ne 0) { Fail "SDK certification failed" }

Write-Host "==> Gate 3/7: PostgreSQL E2E database..."
$ready = docker compose exec -T postgres pg_isready 2>&1
if ($LASTEXITCODE -ne 0 -or ($ready -notmatch "accepting connections")) {
    docker compose up -d
    Start-Sleep -Seconds 3
    $ready = docker compose exec -T postgres pg_isready 2>&1
    if ($LASTEXITCODE -ne 0 -or ($ready -notmatch "accepting connections")) {
        Fail "postgres is not accepting connections"
    }
}
$dbName = "intelligence_maxxxing_stage3_e2e"
docker compose exec -T postgres psql -U intelligence -d postgres -c "DROP DATABASE IF EXISTS $dbName WITH (FORCE)" | Out-Null
docker compose exec -T postgres psql -U intelligence -d postgres -c "CREATE DATABASE $dbName" | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "could not recreate E2E database" }
$env:DATABASE_URL = "postgresql+psycopg://intelligence:intelligence@127.0.0.1:5432/$dbName"
python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Fail "alembic upgrade head failed" }

Write-Host "==> Gate 4/7: register Life app + Stage 3 scopes..."
$boot = python -m intelligence_maxxxing.cli bootstrap-owner --tenant-name "Stage3 Tenant" --owner-name "Stage3 Owner"
if ($LASTEXITCODE -ne 0) { Fail "bootstrap-owner failed" }
$ownerId = ($boot | Select-String "owner_id=(.+)").Matches[0].Groups[1].Value

function New-AppCredential($DisplayName) {
    $reg = python -m intelligence_maxxxing.cli register-application --display-name $DisplayName --owner-id $ownerId
    if ($LASTEXITCODE -ne 0) { Fail "register-application $DisplayName failed" }
    $appId = ($reg | Select-String "application_id=(.+)").Matches[0].Groups[1].Value
    $scopes = @(
        "SUBMIT_OBSERVATION", "READ_AUDIT", "READ_INTELLIGENCE",
        "SUBMIT_HYPOTHESIS", "READ_HYPOTHESIS", "MANAGE_EXPERIMENT",
        "READ_BELIEF", "READ_LEARNING"
    )
    foreach ($s in $scopes) {
        python -m intelligence_maxxxing.cli grant-scope --application-id $appId --scope $s | Out-Null
        if ($LASTEXITCODE -ne 0) { Fail "grant-scope $s failed" }
    }
    $cred = python -m intelligence_maxxxing.cli create-credential --application-id $appId
    if ($LASTEXITCODE -ne 0) { Fail "create-credential failed" }
    return ($cred | Select-String "secret=(.+)").Matches[0].Groups[1].Value
}
$lifeSecret = New-AppCredential "LifeMaxxxing-Stage3"
$otherSecret = New-AppCredential "OtherApp-Stage3"

Write-Host "==> Gate 5/7: install SDK wheel into Life env + Life tests..."
$wheel = Get-ChildItem "$engineRoot\dist\sdk\intelligence_maxxxing_client-*.whl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $wheel) { Fail "SDK wheel not found under dist/sdk" }
pip install --force-reinstall $wheel.FullName | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "pip install SDK wheel failed" }
Push-Location $lifeRoot
$env:PYTHONPATH = "."
python -m unittest tests.test_intelligence
if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "Life backend tests failed" }
Pop-Location

Write-Host "==> Gate 6/7: online + offline Stage 3 canaries..."
$engineProc = Start-Process -PassThru -WindowStyle Hidden -FilePath "python" `
    -WorkingDirectory $engineRoot `
    -ArgumentList "-m", "uvicorn", "--factory", "intelligence_maxxxing.api.app:create_app", "--host", "127.0.0.1", "--port", "$enginePort"
Wait-Healthy "http://127.0.0.1:$enginePort/health/live" "Engine"

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
python scripts/audit/stage3_epistemic_e2e_canaries.py
if ($LASTEXITCODE -ne 0) { Fail "online Stage 3 canaries failed" }

Write-Host "==> Stopping Engine for offline canary..."
Stop-Process -Id $engineProc.Id -Force
Start-Sleep -Seconds 1
$env:E2E_PHASE = "offline"
python scripts/audit/stage3_epistemic_e2e_canaries.py
if ($LASTEXITCODE -ne 0) { Fail "offline Stage 3 canaries failed" }

Stop-Process -Id $lifeProc.Id -Force -ErrorAction SilentlyContinue

Write-Host "==> Gate 7/7: secret scan..."
Push-Location $lifeRoot
$ignored = git check-ignore .env.server 2>$null
if (-not $ignored) { Pop-Location; Fail ".env.server is NOT gitignored" }
$hits = git grep -I -l "imx_sk_" -- ":!tests/" ":!docs/" 2>$null
Pop-Location
if ($hits) { Fail "credential-like string found in tracked LifeMaxxxing files: $hits" }

Cleanup
Write-Host "ALL STAGE 3 EPISTEMIC GATES PASSED" -ForegroundColor Green
exit 0
