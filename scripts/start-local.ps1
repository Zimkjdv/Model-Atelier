$ErrorActionPreference = 'Stop'
$atelierWorkspace = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $atelierWorkspace
$atelierPython = Join-Path $atelierWorkspace '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $atelierPython)) { throw 'Please create .venv and install requirements/runtime.lock.txt. See README.md.' }
if (-not (Test-Path -LiteralPath 'frontend\dist\index.html')) { throw 'Please run npm.cmd ci and npm.cmd run build in frontend first.' }
$atelierPromptProcess = $null
if (Test-Path -LiteralPath (Join-Path $atelierWorkspace 'runtime\prompt-llm\ollama\ollama.exe')) {
    try { $atelierPromptProcess = & (Join-Path $atelierWorkspace 'scripts\start-prompt-llm.ps1') -Background }
    catch { Write-Warning "Optional prompt converter could not start: $_" }
}
try {
    & $atelierPython -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers --timeout-graceful-shutdown 5
} finally {
    if ($atelierPromptProcess -and -not $atelierPromptProcess.HasExited) {
        Stop-Process -Id $atelierPromptProcess.Id -ErrorAction SilentlyContinue
    }
}
