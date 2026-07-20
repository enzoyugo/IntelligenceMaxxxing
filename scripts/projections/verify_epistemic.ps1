# Verify epistemic projections via in-memory ledger replay (live untouched).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))

if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
        $name, $value = $_.Split('=', 2)
        Set-Item -Path "Env:$name" -Value $value
    }
}

Write-Host "Verifying epistemic projections (non-destructive memory compare)..."
python -m intelligence_maxxxing.cli verify-epistemic
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Epistemic projection verification complete (live projection untouched)."
