[CmdletBinding()]
param(
    [int]$Port = 8501,
    [string]$AccessPin = "",
    [string]$CodexModel = "gpt-5.6-terra"
)

$ErrorActionPreference = "Stop"
$cloudflaredPath = Join-Path $PSScriptRoot ".tools\cloudflared.exe"
$codexDir = Join-Path $PSScriptRoot ".tools\codex-cli"
$codexPath = Get-ChildItem -LiteralPath $codexDir -Recurse -Filter "codex.exe" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match "vendor.*bin.*codex.exe$" } |
    Select-Object -First 1 -ExpandProperty FullName
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not $codexPath -or -not (Test-Path -LiteralPath $cloudflaredPath) -or -not (Test-Path -LiteralPath $venvPython)) {
    throw "Local components are missing. Run setup_local.ps1 first."
}

& $codexPath login status
if ($LASTEXITCODE -ne 0) {
    throw "Codex is not signed in with ChatGPT. Run setup_local.ps1 again."
}

if (-not $AccessPin) {
    $AccessPin = Get-Random -Minimum 100000 -Maximum 1000000
}

$env:CUTLENS_AI_BACKEND = "codex"
$env:CODEX_CLI_PATH = $codexPath
$env:CODEX_VISION_MODEL = $CodexModel
$env:USDA_API_KEY = "DEMO_KEY"
$env:CUTLENS_ACCESS_PIN = [string]$AccessPin

$streamlitArguments = @(
    "-m", "streamlit", "run", "app.py",
    "--server.address", "127.0.0.1",
    "--server.port", [string]$Port,
    "--server.headless", "true"
)

$streamlitProcess = Start-Process `
    -FilePath $venvPython `
    -ArgumentList $streamlitArguments `
    -WorkingDirectory $PSScriptRoot `
    -WindowStyle Hidden `
    -PassThru

$appReady = $false
for ($attempt = 0; $attempt -lt 45; $attempt++) {
    Start-Sleep -Seconds 1
    try {
        Invoke-WebRequest -Uri "http://127.0.0.1:$Port/_stcore/health" -UseBasicParsing -TimeoutSec 2 | Out-Null
        $appReady = $true
        break
    } catch {
        if ($streamlitProcess.HasExited) {
            throw "Streamlit failed. Run .venv\Scripts\python -m streamlit run app.py in this folder to inspect the error."
        }
    }
}

if (-not $appReady) {
    if (-not $streamlitProcess.HasExited) {
        Stop-Process -Id $streamlitProcess.Id
    }
    throw "Streamlit startup timed out."
}

Write-Host ""
Write-Host "CutLens is running with your ChatGPT/Codex workspace entitlement." -ForegroundColor Green
Write-Host "Phone access PIN: $AccessPin" -ForegroundColor Yellow
Write-Host "Open the https://...trycloudflare.com URL shown below in Safari." -ForegroundColor Cyan
Write-Host "Keep this window and computer running. Press Ctrl+C to stop sharing."
Write-Host ""

try {
    & $cloudflaredPath tunnel --url "http://127.0.0.1:$Port" --no-autoupdate
} finally {
    if (-not $streamlitProcess.HasExited) {
        Stop-Process -Id $streamlitProcess.Id
    }
}
