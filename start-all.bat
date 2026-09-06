@echo off
setlocal
cd /d "%~dp0"

where powershell.exe >nul 2>&1
if errorlevel 1 (
  echo 找不到 Windows PowerShell，請直接執行 start-local.ps1 與 start-comfyui.ps1。
  pause
  exit /b 1
)

start "Model Atelier - Platform 8000" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-local.ps1"
start "Model Atelier - ComfyUI 8188" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-comfyui.ps1"

echo 已開啟兩個服務視窗：平台 8000、ComfyUI 8188。
echo 關閉時請在各自視窗按 Ctrl+C，確認服務停止後再關閉視窗。
endlocal
