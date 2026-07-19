# Applies all pending Alembic migrations to the configured database.
$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

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
}

Write-Host "Applying migrations to: $env:DATABASE_URL" -ForegroundColor Cyan
python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Write-Error "alembic upgrade failed" }
Write-Host "Database is at head." -ForegroundColor Green
