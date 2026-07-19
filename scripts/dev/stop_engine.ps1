# Stops the Engine process listening on ENGINE_PORT (default 8100).
# Only kills the specific process bound to that port; nothing else.
$ErrorActionPreference = "Stop"

$enginePort = if ($env:ENGINE_PORT) { [int]$env:ENGINE_PORT } else { 8100 }

$connections = Get-NetTCPConnection -LocalPort $enginePort -State Listen -ErrorAction SilentlyContinue
if (-not $connections) {
    Write-Host "No process is listening on port $enginePort. Nothing to stop."
    exit 0
}

$stopped = @()
foreach ($conn in $connections) {
    $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    if ($process -and $process.ProcessName -match "python|uvicorn") {
        Write-Host "Stopping $($process.ProcessName) (PID $($process.Id)) on port $enginePort"
        Stop-Process -Id $process.Id -Force
        $stopped += $process.Id
    } elseif ($process) {
        Write-Warning "Process on port $enginePort is '$($process.ProcessName)' (PID $($process.Id)); not a Python/uvicorn process, refusing to kill it."
    }
}

if ($stopped.Count -gt 0) {
    Write-Host "Engine stopped." -ForegroundColor Green
}
