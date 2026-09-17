# ==============================================================================
# JasoForge Installer for Windows (PowerShell 5.1+ / PowerShell 7+)
# Enterprise-Grade Technical Resume & Engineering Narrative Verification Engine
# ==============================================================================

[CmdletBinding()]
param(
    [string]$Target = "all",
    [switch]$Symlink,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  🔥 JasoForge Installer (Windows PowerShell)                    " -ForegroundColor Cyan
Write-Host "  Deterministic Resume Vetting & Engineering Narrative Engine   " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# Locate Python
$PythonExe = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonExe = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonExe = "py -3"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $PythonExe = "python3"
} else {
    Write-Error "❌ Error: Python 3 was not found in PATH. Please install Python from https://www.python.org/ or Windows Store."
    exit 1
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($ScriptDir -and (Test-Path (Join-Path $ScriptDir "installer.py"))) {
    Write-Host "⚡ Running local installer..." -ForegroundColor Green
    $ArgsList = @((Join-Path $ScriptDir "installer.py"), "--target", $Target)
    if ($Symlink) { $ArgsList += "--symlink" }
    if ($DryRun) { $ArgsList += "--dry-run" }
    & $PythonExe @ArgsList
} else {
    Write-Host "🌐 Remote installation detected. Fetching latest release..." -ForegroundColor Yellow
    $TempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("jasoforge_" + [System.Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $TempDir -Force | Out-Null

    try {
        $ZipUrl = "https://github.com/choosla/jasoforge/archive/refs/heads/main.zip"
        $ZipPath = Join-Path $TempDir "jasoforge.zip"
        Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipPath -UseBasicParsing
        Expand-Archive -Path $ZipPath -DestinationPath $TempDir -Force
        
        $Extracted = Get-ChildItem -Path $TempDir -Directory | Select-Object -First 1
        $InstallerScript = Join-Path $Extracted.FullName "installer.py"
        
        $ArgsList = @($InstallerScript, "--target", $Target)
        if ($Symlink) { $ArgsList += "--symlink" }
        if ($DryRun) { $ArgsList += "--dry-run" }
        & $PythonExe @ArgsList
    } finally {
        if (Test-Path $TempDir) {
            Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
