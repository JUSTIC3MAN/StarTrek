# ClaudeComfy one-time setup for the MiniMax H3 workflows (DaSiWa + Seed Hunter).
# 1. Creates a Python 3.12 environment in A:\ClaudeComfy\venv (your main ComfyUI is not touched)
# 2. Installs PyTorch 2.10 CUDA 13.0, ComfyUI v0.39.2 requirements, ComfyUI-Manager and the custom node packages
# 3. Downloads the MiniMax H3 VAEs, text encoder, preview decoder, latent upscaler and turbo LoRAs
# 4. Test-starts ComfyUI once so every custom node import is checked
# Safe to run again: finished steps and finished downloads are skipped.

$ErrorActionPreference = 'Stop'
$Scripts    = $PSScriptRoot
$Root       = Split-Path -Parent $Scripts
$Log        = Join-Path $Root 'setup_log.txt'
$UV         = Join-Path $Root 'tools\uv.exe'
$Venv       = Join-Path $Root 'venv'
$Py         = Join-Path $Venv 'Scripts\python.exe'
$Comfy      = Join-Path $Root 'ComfyUI'
$TorchIndex = 'https://download.pytorch.org/whl/cu130'

$env:UV_LINK_MODE     = 'copy'
$env:UV_HTTP_TIMEOUT  = '600'
$env:PYTHONUTF8       = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONNOUSERSITE = '1'

Set-Content -Path $Log -Value ("ClaudeComfy setup log - " + (Get-Date)) -Encoding UTF8

function Log([string]$Text, [string]$Color = '') {
    if ($Color) { Write-Host $Text -ForegroundColor $Color } else { Write-Host $Text }
    Add-Content -Path $Log -Value $Text -Encoding UTF8
}
function Step([string]$Text) { Log ''; Log ("=== " + $Text + " ===") 'Cyan' }

# Runs a program, shows its output and copies it into setup_log.txt. Returns the exit code.
function Run([string]$Exe, [string[]]$Argv) {
    Log ("> " + (Split-Path -Leaf $Exe) + " " + ($Argv -join ' ')) 'DarkGray'
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $Exe @Argv 2>&1 | ForEach-Object { Log ("" + $_) }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    return $code
}
function RunOrFail([string]$Exe, [string[]]$Argv) {
    $code = Run $Exe $Argv
    if ($code -ne 0) { throw ("'" + (Split-Path -Leaf $Exe) + "' failed with exit code " + $code) }
}

try {
    if (-not (Test-Path $UV)) { throw "tools\uv.exe is missing." }

    Step 'GPU'
    try { $null = Run 'nvidia-smi' @('--query-gpu=name,driver_version,memory.total', '--format=csv,noheader') }
    catch { Log 'nvidia-smi not found on PATH (continuing).' 'Yellow' }

    Step 'Python 3.12 environment'
    if (Test-Path $Py) { Log 'venv already exists - reusing it.' }
    else { RunOrFail $UV @('venv', $Venv, '--python', '3.12', '--seed') }

    Step 'PyTorch 2.10 + CUDA 13.0 (about 3 GB the first time, no progress bar - give it a few minutes)'
    RunOrFail $UV @('pip', 'install', '--python', $Py, '--index-url', $TorchIndex,
                    'torch==2.10.0+cu130', 'torchvision==0.25.0+cu130', 'torchaudio==2.11.0+cu130')

    $common = @('pip', 'install', '--python', $Py, '-c', (Join-Path $Scripts 'constraints.txt'),
                '--extra-index-url', $TorchIndex, '--index-strategy', 'unsafe-best-match')

    Step 'ComfyUI v0.39.2 requirements'
    RunOrFail $UV ($common + @('-r', (Join-Path $Comfy 'requirements.txt')))

    Step 'ComfyUI-Manager'
    RunOrFail $UV ($common + @('-r', (Join-Path $Comfy 'manager_requirements.txt')))

    Step 'Custom node requirements'
    RunOrFail $UV ($common + @('-r', (Join-Path $Scripts 'node_requirements.txt')))

    Step 'Optional: NVIDIA Video Effects bindings (only the DaSiWa "RTX Upscaler & Refiner" toggle uses them)'
    $code = Run $UV ($common + @('nvidia-vfx==0.1.0.1'))
    if ($code -ne 0) { Log 'nvidia-vfx did not install. Everything else works; only that optional toggle needs it.' 'Yellow' }

    Step 'Checking PyTorch can see the GPU'
    RunOrFail $Py @((Join-Path $Scripts 'check_env.py'))

    Step 'MiniMax H3 model downloads (about 27 GB - progress shows below, its own log is download_log.txt)'
    & $Py (Join-Path $Scripts 'download_h3_models.py')
    if ($LASTEXITCODE -ne 0) { throw 'Some model downloads did not finish. Run this setup again to resume them.' }
    Log 'Model downloads finished.'

    Step 'Test start of ComfyUI (loads every custom node, then exits)'
    Push-Location $Comfy
    try { $code = Run $Py @('-s', 'main.py', '--quick-test-for-ci', '--enable-manager', '--port', '8189') }
    finally { Pop-Location }
    if ($code -ne 0) { throw 'ComfyUI test start failed - see setup_log.txt.' }

    Step 'Done'
    Log 'Setup finished. Start ComfyUI with "2 - Start ClaudeComfy.bat" (it opens on http://127.0.0.1:8189).' 'Green'
    Log 'Your workflows are in the Workflows sidebar: "DaSiWa MiniMax H3 (ClaudeComfy)" and "MiniMax H3 Seed Hunter (ClaudeComfy)".' 'Green'
}
catch {
    Log ''
    Log ("SETUP STOPPED: " + $_.Exception.Message) 'Red'
    Log ("Full log: " + $Log) 'Red'
    exit 1
}
