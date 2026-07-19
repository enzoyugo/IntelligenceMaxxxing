# Governed destructive downgrade. Blocked by default.
# Requires ALL of:
#   ENGINE_DESTRUCTIVE_MIGRATIONS_ALLOWED=true
#   ENGINE_MAINTENANCE_MODE=true
#   ENGINE_CONFIRMED_BACKUP_ID=<verified backup id>
#   -ActorHasAdminister
#   -ConfirmPhrase "I UNDERSTAND THIS DESTROYS HISTORY"
# See docs/runbooks/MIGRATION_SAFETY.md
param(
    [string]$Revision = "-1",
    [switch]$ActorHasAdminister,
    [string]$ConfirmPhrase = ""
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))

if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
        $name, $value = $_.Split('=', 2)
        Set-Item -Path "Env:$name" -Value $value
    }
}

$allowed = $env:ENGINE_DESTRUCTIVE_MIGRATIONS_ALLOWED
$maintenance = $env:ENGINE_MAINTENANCE_MODE
$backupId = $env:ENGINE_CONFIRMED_BACKUP_ID
$requiredPhrase = "I UNDERSTAND THIS DESTROYS HISTORY"

$blockers = @()
if ($allowed -ne "true") { $blockers += "ENGINE_DESTRUCTIVE_MIGRATIONS_ALLOWED is not true" }
if ($maintenance -ne "true") { $blockers += "ENGINE_MAINTENANCE_MODE is not true" }
if ([string]::IsNullOrWhiteSpace($backupId)) { $blockers += "ENGINE_CONFIRMED_BACKUP_ID is missing" }
if (-not $ActorHasAdminister) { $blockers += "actor lacks ADMINISTER_ENGINE" }
if ($ConfirmPhrase -ne $requiredPhrase) { $blockers += "confirm phrase does not match" }

if ($blockers.Count -gt 0) {
    Write-Host "DESTRUCTIVE DOWNGRADE BLOCKED:" -ForegroundColor Red
    foreach ($b in $blockers) { Write-Host "  - $b" -ForegroundColor Red }
    exit 2
}

Write-Host "Safety policy authorized. Proceeding with alembic downgrade to $Revision"
Write-Host "Confirmed backup id: $backupId"
python -m alembic downgrade $Revision
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Downgrade complete."
