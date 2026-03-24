$ErrorActionPreference = "Stop"

$uri = "http://127.0.0.1:8000/spotify/save-history"
$logDir = "C:\Users\paulg\projet-pro\backend\logs"
$logFile = Join-Path $logDir "sync-history.log"

if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

try {
    $result = Invoke-RestMethod -Method Post -Uri $uri
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logFile -Value "$timestamp | OK | $($result | ConvertTo-Json -Compress)"
} catch {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logFile -Value "$timestamp | ERROR | $($_.Exception.Message)"
}
