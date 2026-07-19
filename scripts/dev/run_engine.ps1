# Runs the IntelligenceMaxxxing Engine (FastAPI) in the foreground.
$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

# 1. Load .env when it exists (without overriding already-set variables)
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$") {
            $name = $Matches[1]
            $value = $Matches[2]
            if (-not [Environment]::GetEnvironmentVariable($name)) {
                [Environment]::SetEnvironmentVariable($name, $value)
            }
        }
    }
    Write-Host "Loaded environment from .env"
}

$engineHost = if ($env:ENGINE_HOST) { $env:ENGINE_HOST } else { "127.0.0.1" }
$enginePort = if ($env:ENGINE_PORT) { $env:ENGINE_PORT } else { "8100" }

# 2. Validate dependencies
python -c "import fastapi, sqlalchemy, alembic, uvicorn, pydantic" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Missing dependencies. Run scripts\dev\setup_engine.ps1 first."
}

# 3. Verify / apply migrations (warn if database is unreachable; health will report it)
Write-Host "Checking database migrations..."
python -m alembic upgrade head 2>&1 | Out-String | Write-Host
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Could not apply migrations (database unreachable?). The Engine will start anyway and /api/v1/health will report the database as UNHEALTHY."
}

# 4. Start FastAPI
Write-Host ""
Write-Host "Starting IntelligenceMaxxxing Engine" -ForegroundColor Green
Write-Host "  Health:  http://${engineHost}:${enginePort}/api/v1/health"
Write-Host "  OpenAPI: http://${engineHost}:${enginePort}/docs"
Write-Host ""
python -m uvicorn --factory intelligence_maxxxing.api.app:create_app --host $engineHost --port $enginePort
