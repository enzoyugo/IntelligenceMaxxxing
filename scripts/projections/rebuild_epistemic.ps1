# Rebuild Stage 3 epistemic projections from the event store (never deletes events).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))

if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
        $name, $value = $_.Split('=', 2)
        Set-Item -Path "Env:$name" -Value $value
    }
}

Write-Host "Rebuilding epistemic projections from engine_events..."
python -m intelligence_maxxxing.cli rebuild-epistemic
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Epistemic projection rebuild complete."
