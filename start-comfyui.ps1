$ErrorActionPreference = 'Stop'
$atelierComfy = Join-Path $PSScriptRoot 'runtime\ComfyUI'
$atelierComfyPython = Join-Path $atelierComfy '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $atelierComfyPython)) { throw 'ComfyUI environment not found. See README.md.' }
$atelierPathExporter = Join-Path $PSScriptRoot 'scripts\comfy_model_paths.py'
$atelierPathExportOutput = @(& $atelierComfyPython $atelierPathExporter)
$atelierPathExportExitCode = $LASTEXITCODE
if ($atelierPathExportExitCode -ne 0) { throw 'Local checkpoint directory export failed. ComfyUI was not started; fix the saved directories and retry.' }
$atelierExpectedConfig = Join-Path $PSScriptRoot 'runtime\comfy-extra-model-paths.json'
if ($atelierPathExportOutput.Count -ne 1 -or [string]$atelierPathExportOutput[0] -ne $atelierExpectedConfig -or -not (Test-Path -LiteralPath $atelierExpectedConfig -PathType Leaf)) { throw 'Local checkpoint directory exporter returned an invalid config path. ComfyUI was not started.' }
$atelierExtraConfig = [string]$atelierPathExportOutput[0]
$atelierStopVerifier = Join-Path $PSScriptRoot 'scripts\comfy_stop_capability.py'
$atelierStopResult = @(& $atelierComfyPython $atelierStopVerifier)
if ($LASTEXITCODE -ne 0) { throw 'Targeted stop capability check failed. ComfyUI was not started.' }
$atelierStopCapability = ($atelierStopResult -join '') | ConvertFrom-Json
$atelierStopArgs = @()
if ($atelierStopCapability.supported -eq $true -and $atelierStopCapability.feature_flag -eq 'model_atelier_atomic_job_cancel_v1=15eb748b3ec5f8a0a2d470b7fb280e2d7579f916') {
    $atelierStopArgs = @('--feature-flag', [string]$atelierStopCapability.feature_flag)
} else { Write-Host 'Targeted running-job stop is unavailable for this ComfyUI source; normal generation remains available.' }
Set-Location -LiteralPath $atelierComfy
& $atelierComfyPython main.py --listen 127.0.0.1 --port 8188 --disable-auto-launch --disable-api-nodes --extra-model-paths-config $atelierExtraConfig @atelierStopArgs
