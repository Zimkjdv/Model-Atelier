param(
    [ValidateRange(1, 300)]
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = 'Stop'
$atelierUrl = 'http://127.0.0.1:8000/'
$atelierDeadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
$atelierReady = $false
Write-Host 'Waiting for the platform before opening the browser...'

while ([DateTime]::UtcNow -lt $atelierDeadline) {
    try {
        $atelierHealth = Invoke-RestMethod -Uri ($atelierUrl + 'api/health') -TimeoutSec 2
        if ($atelierHealth.status -eq 'ok') {
            $atelierPage = Invoke-WebRequest -Uri $atelierUrl -UseBasicParsing -TimeoutSec 2
            if ($atelierPage.StatusCode -eq 200 -and $atelierPage.Headers['Content-Type'] -like 'text/html*') {
                $atelierReady = $true
                break
            }
        }
    } catch {
        # The service may still be starting. Retry only the readiness checks.
    }
    Start-Sleep -Milliseconds 250
}

if (-not $atelierReady) {
    Write-Host 'The platform did not become ready. Check its service window, then open http://127.0.0.1:8000/ manually.'
    exit 1
}

try {
    Start-Process -FilePath $atelierUrl -ErrorAction Stop
} catch {
    Write-Host 'Could not open the default browser. Open http://127.0.0.1:8000/ manually.'
    exit 1
}
