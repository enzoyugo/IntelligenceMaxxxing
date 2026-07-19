# Sets up the IntelligenceMaxxxing Engine development environment.
$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

Write-Host "== IntelligenceMaxxxing Engine setup ==" -ForegroundColor Cyan

# 1. Python version check
$pythonVersion = python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
if ([version]$pythonVersion -lt [version]"3.12") {
    Write-Error "Python 3.12+ is required. Found: $pythonVersion"
}
Write-Host "Python $pythonVersion OK"

# 2. Install package with dev extras
Write-Host "Installing package (editable, dev extras)..."
python -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed" }

# 3. Create .env from example if missing
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example (adjust DATABASE_URL if needed)"
} else {
    Write-Host ".env already exists; not overwritten"
}

Write-Host ""
Write-Host "Setup complete. Next steps:" -ForegroundColor Green
Write-Host "  1. scripts\dev\start_postgres.ps1   (requires Docker)"
Write-Host "  2. scripts\dev\run_engine.ps1"
