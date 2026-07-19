# Starts the local PostgreSQL container for the Engine.
$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed or not on PATH. Install Docker Desktop, or point DATABASE_URL at an existing PostgreSQL instance."
}

Write-Host "Starting PostgreSQL via docker compose..." -ForegroundColor Cyan
docker compose up -d postgres
if ($LASTEXITCODE -ne 0) { Write-Error "docker compose up failed" }

Write-Host "Waiting for PostgreSQL to become healthy..."
$deadline = (Get-Date).AddSeconds(60)
do {
    Start-Sleep -Seconds 2
    $status = docker inspect --format "{{.State.Health.Status}}" intelligence_maxxxing_postgres 2>$null
} while ($status -ne "healthy" -and (Get-Date) -lt $deadline)

if ($status -ne "healthy") {
    Write-Error "PostgreSQL did not become healthy within 60 seconds (status: $status)"
}
Write-Host "PostgreSQL is healthy on 127.0.0.1:5432 (db: intelligence_maxxxing)" -ForegroundColor Green
