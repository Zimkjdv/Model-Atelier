$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$atelierPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $atelierPython)) { throw 'Please create .venv and install requirements.lock.txt. See README.md.' }
if (-not (Test-Path -LiteralPath 'frontend\dist\index.html')) { throw 'Please run npm.cmd ci and npm.cmd run build in frontend first.' }
$atelierPromptProcess = $null
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'runtime\prompt-llm\ollama\ollama.exe')) {
    try { $atelierPromptProcess = & (Join-Path $PSScriptRoot 'start-prompt-llm.ps1') -Background }
    catch { Write-Warning "Optional prompt converter could not start: $_" }
}
try {
    & $atelierPython -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers --timeout-graceful-shutdown 5
} finally {
    if ($atelierPromptProcess -and -not $atelierPromptProcess.HasExited) {
        Stop-Process -Id $atelierPromptProcess.Id -ErrorAction SilentlyContinue
    }
}
