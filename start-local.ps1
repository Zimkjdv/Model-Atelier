$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$atelierPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $atelierPython)) { throw 'Please create .venv and install requirements.lock.txt. See README.md.' }
if (-not (Test-Path -LiteralPath 'frontend\dist\index.html')) { throw 'Please run npm.cmd ci and npm.cmd run build in frontend first.' }
& $atelierPython -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
