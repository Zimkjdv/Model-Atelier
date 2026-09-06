$ErrorActionPreference = 'Stop'
$atelierComfy = Join-Path $PSScriptRoot 'runtime\ComfyUI'
$atelierComfyPython = Join-Path $atelierComfy '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $atelierComfyPython)) { throw 'ComfyUI environment not found. See README.md.' }
Set-Location -LiteralPath $atelierComfy
& $atelierComfyPython main.py --listen 127.0.0.1 --port 8188 --disable-auto-launch --disable-api-nodes
