# Stage 1 performance bounds measurement (not a pass/fail gate).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))

if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
        $name, $value = $_.Split('=', 2)
        Set-Item -Path "Env:$name" -Value $value
    }
}

$env:PYTHONPATH = (Get-Location).Path
python tests/benchmarks/stage1_bounds.py
exit $LASTEXITCODE
