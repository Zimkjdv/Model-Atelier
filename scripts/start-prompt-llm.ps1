param([switch]$Background)
$ErrorActionPreference = 'Stop'
$atelierWorkspace = Split-Path -Parent $PSScriptRoot
try {
    $atelierVersion = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
    if ($atelierVersion.version) {
        Write-Host 'Ollama is already running on 127.0.0.1:11434.'
        return
    }
} catch { }
$atelierOllama = Join-Path $atelierWorkspace 'runtime\prompt-llm\ollama\ollama.exe'
if (-not (Test-Path -LiteralPath $atelierOllama)) {
    throw 'Portable Ollama is not installed. Install Ollama and run ollama serve, or see docs/features/prompt-converter.md.'
}
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = Join-Path $atelierWorkspace 'runtime\prompt-llm\models'
$env:OLLAMA_NO_CLOUD = '1'
if ($Background) {
    return Start-Process -FilePath $atelierOllama -ArgumentList 'serve' -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $atelierWorkspace 'runtime\prompt-llm\serve.log') -RedirectStandardError (Join-Path $atelierWorkspace 'runtime\prompt-llm\serve-error.log')
}
& $atelierOllama serve
exit $LASTEXITCODE
