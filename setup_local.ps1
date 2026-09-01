[CmdletBinding()]
param(
    [string]$CodexVersion = "0.152.0"
)

$ErrorActionPreference = "Stop"
$toolsDir = Join-Path $PSScriptRoot ".tools"
New-Item -ItemType Directory -Path $toolsDir -Force | Out-Null

Write-Host "[1/4] Installing the portable Cloudflare HTTPS tunnel..." -ForegroundColor Cyan
$cloudflaredPath = Join-Path $toolsDir "cloudflared.exe"
if (-not (Test-Path -LiteralPath $cloudflaredPath)) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest `
        -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" `
        -OutFile $cloudflaredPath `
        -UseBasicParsing
}

Write-Host "[2/4] Installing the official Codex CLI..." -ForegroundColor Cyan
$codexDir = Join-Path $toolsDir "codex-cli"
$codexPath = Get-ChildItem -LiteralPath $codexDir -Recurse -Filter "codex.exe" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match "vendor.*bin.*codex.exe$" } |
    Select-Object -First 1 -ExpandProperty FullName

if (-not $codexPath) {
    $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npmCommand) {
        $npmCandidate = "$env:ProgramFiles\nodejs\npm.cmd"
        if (Test-Path -LiteralPath $npmCandidate) {
            $npmCommand = Get-Item -LiteralPath $npmCandidate
        }
    }

    if (-not $npmCommand) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            throw "Node.js is required and winget was not found. Install Node.js LTS first."
        }
        winget install --exact --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements --silent
        if ($LASTEXITCODE -ne 0) {
            throw "Node.js installation failed. winget exit code: $LASTEXITCODE"
        }
        $npmCandidate = "$env:ProgramFiles\nodejs\npm.cmd"
        if (-not (Test-Path -LiteralPath $npmCandidate)) {
            throw "Node.js was installed, but npm.cmd was not found. Reopen PowerShell and run this script again."
        }
        $npmCommand = Get-Item -LiteralPath $npmCandidate
    }

    & $npmCommand.FullName install --prefix $codexDir "@openai/codex@$CodexVersion"
    if ($LASTEXITCODE -ne 0) {
        throw "Codex CLI installation failed. npm exit code: $LASTEXITCODE"
    }

    $codexPath = Get-ChildItem -LiteralPath $codexDir -Recurse -Filter "codex.exe" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match "vendor.*bin.*codex.exe$" } |
        Select-Object -First 1 -ExpandProperty FullName
}

if (-not $codexPath) {
    throw "Codex CLI executable was not found after installation."
}
& $codexPath --version

Write-Host "[3/4] Checking ChatGPT sign-in..." -ForegroundColor Cyan
& $codexPath login status
if ($LASTEXITCODE -ne 0) {
    Write-Host "A browser window will open. Sign in with your ChatGPT Enterprise account." -ForegroundColor Yellow
    & $codexPath login
    if ($LASTEXITCODE -ne 0) {
        throw "Codex ChatGPT sign-in was not completed."
    }
}

Write-Host "[4/4] Creating the Python environment and installing CutLens..." -ForegroundColor Cyan
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    py -3.10 -m venv (Join-Path $PSScriptRoot ".venv")
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the Python environment."
    }
}
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Python dependency installation failed."
}

Write-Host ""
Write-Host "Setup complete. Run start_local.ps1 whenever you want to use CutLens." -ForegroundColor Green
