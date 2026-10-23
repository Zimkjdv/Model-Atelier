@echo off
setlocal
cd /d "%~dp0"

where powershell.exe >nul 2>&1
if errorlevel 1 (
  echo Windows PowerShell was not found. See docs/setup-and-operations.md.
  pause
  exit /b 1
)

start "Model Atelier - Platform 8000" powershell.exe -NoExit -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-local.ps1"
start "Model Atelier - ComfyUI 8188" powershell.exe -NoExit -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-comfyui.ps1"

echo Opened service windows: platform 8000 and ComfyUI 8188.
echo Check each window for readiness or startup errors.
echo To stop, press Ctrl+C in each window and wait before closing it.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\open-platform.ps1"
if errorlevel 1 (
  pause
  exit /b 1
)
endlocal
