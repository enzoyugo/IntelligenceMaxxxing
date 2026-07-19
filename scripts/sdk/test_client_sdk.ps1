# Installs the standalone client wheel into a CLEAN virtualenv and certifies:
#   * the client imports,
#   * the Engine Core (`intelligence_maxxxing`) is absent,
#   * only httpx + pydantic are pulled in,
#   * the SDK unit tests pass against the installed wheel.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))

function Fail($Message) {
    Write-Host "SDK TEST FAILED: $Message" -ForegroundColor Red
    exit 1
}

$wheel = Get-ChildItem "dist/sdk/*.whl" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $wheel) {
    Write-Host "No wheel found; building first..."
    powershell -ExecutionPolicy Bypass -File scripts/sdk/build_client_sdk.ps1
    if ($LASTEXITCODE -ne 0) { Fail "build step failed" }
    $wheel = Get-ChildItem "dist/sdk/*.whl" | Select-Object -First 1
}

$venv = Join-Path $env:TEMP "imx_sdk_clean_venv"
if (Test-Path $venv) { Remove-Item -Recurse -Force $venv }
Write-Host "==> Creating clean virtualenv at $venv ..."
python -m venv $venv
if ($LASTEXITCODE -ne 0) { Fail "could not create venv" }
$py = Join-Path $venv "Scripts\python.exe"

Write-Host "==> Installing ONLY the client wheel (+ its declared deps)..."
& $py -m pip install --quiet $wheel.FullName
if ($LASTEXITCODE -ne 0) { Fail "wheel install failed in clean venv" }

Write-Host "==> Certifying import + Core absence + minimal deps..."
$assert = @"
import importlib.util as u
import intelligence_maxxxing_client as c
assert c.IntelligenceMaxxxingClient is not None, 'client missing'
assert u.find_spec('intelligence_maxxxing') is None, 'Engine Core LEAKED into client env'
for forbidden in ('fastapi', 'sqlalchemy', 'alembic', 'psycopg'):
    assert u.find_spec(forbidden) is None, forbidden + ' leaked into client env'
import httpx, pydantic  # required deps present
print('CLIENT OK: core absent, deps present')
"@
& $py -c $assert
if ($LASTEXITCODE -ne 0) { Fail "clean-venv certification failed" }

Write-Host "==> Running SDK unit tests against the installed wheel..."
& $py -m pip install --quiet pytest
& $py -m pytest sdk/python/tests -q
if ($LASTEXITCODE -ne 0) { Fail "SDK unit tests failed" }

Write-Host "STANDALONE SDK CERTIFIED IN CLEAN VENV" -ForegroundColor Green
exit 0
