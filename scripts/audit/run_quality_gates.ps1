# Runs every Stage 0 quality gate. Fails fast and loudly.
$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$failures = @()

function Invoke-Gate {
    param([string]$Name, [scriptblock]$Command)
    Write-Host ""
    Write-Host "== GATE: $Name ==" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        $script:failures += $Name
        Write-Host "GATE FAILED: $Name" -ForegroundColor Red
    } else {
        Write-Host "GATE PASSED: $Name" -ForegroundColor Green
    }
}

Invoke-Gate "ruff lint"            { python -m ruff check . }
Invoke-Gate "ruff format"          { python -m ruff format --check . }
Invoke-Gate "mypy"                 { python -m mypy src sdk }
Invoke-Gate "import boundaries"    { lint-imports }
Invoke-Gate "constitutional tests" { python -m pytest tests/constitutional -q }
Invoke-Gate "contract tests"       { python -m pytest tests/contract -q }
Invoke-Gate "full test suite"      { python -m pytest -q }
Invoke-Gate "constitution manifest" {
    powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "verify_constitution.ps1")
}

Write-Host ""
if ($failures.Count -gt 0) {
    Write-Host "QUALITY GATES FAILED: $($failures -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "ALL QUALITY GATES PASSED" -ForegroundColor Green
exit 0
