#Requires -RunAsAdministrator
<#
.SYNOPSIS
  One-time Windows prerequisites for the VIO Docker stack (OAK-D camera feed).

.DESCRIPTION
  Installs / enables:
    1. WSL 2 + Ubuntu (Docker Desktop backend)
    2. Docker Desktop (WSL 2 engine)
    3. usbipd-win (pass OAK-D USB into WSL)

  After this script finishes, reboot if prompted, open Docker Desktop once,
  then run:  windows\build.bat
#>

$ErrorActionPreference = "Stop"

Write-Host "=== VIO Docker — Windows prerequisite install ===" -ForegroundColor Cyan

function Ensure-WingetPackage {
    param(
        [Parameter(Mandatory = $true)][string]$Id,
        [Parameter(Mandatory = $true)][string]$Name
    )
    Write-Host "`n[ ] Checking $Name ($Id)..." -ForegroundColor Yellow
    $list = winget list --id $Id --accept-source-agreements 2>$null
    if ($LASTEXITCODE -eq 0 -and ($list -join "`n") -match [regex]::Escape($Id)) {
        Write-Host "[OK] $Name already installed." -ForegroundColor Green
        return
    }
    Write-Host "[+] Installing $Name..." -ForegroundColor Yellow
    winget install --id $Id -e --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install $Name (winget exit $LASTEXITCODE)"
    }
    Write-Host "[OK] $Name installed." -ForegroundColor Green
}

# 1) WSL 2
Write-Host "`n[1/3] Enabling WSL 2..." -ForegroundColor Cyan
wsl --install --no-distribution
# Prefer Ubuntu as default distro for Docker / usbipd attach targets
try {
    wsl --install -d Ubuntu --no-launch
} catch {
    Write-Host "[WARN] Ubuntu distro install may need a reboot first: $_" -ForegroundColor Yellow
}

# 2) Docker Desktop
Ensure-WingetPackage -Id "Docker.DockerDesktop" -Name "Docker Desktop"

# 3) usbipd-win (OAK-D → WSL)
Ensure-WingetPackage -Id "dorssel.usbipd-win" -Name "usbipd-win"

# Outputs folder for camera / VIO logs
$repoRoot = Split-Path -Parent $PSScriptRoot
$outputs = Join-Path $repoRoot "outputs"
New-Item -ItemType Directory -Force -Path $outputs | Out-Null
Write-Host "`n[OK] outputs folder: $outputs" -ForegroundColor Green

Write-Host @"

=== Next steps ===
1. REBOOT if Windows asked you to (required after first WSL install).
2. Open Docker Desktop once and wait until the engine is green.
   Settings → General → Use the WSL 2 based engine (enabled).
3. Plug in the OAK-D camera.
4. In an elevated PowerShell, attach the camera to WSL:
     cd "$repoRoot\windows"
     .\attach_oak.ps1
5. Build the VIO image (first build takes a long time):
     .\build.bat
6. Run the live camera VIO stack:
     .\run.bat

Pose / depth / features land under: $outputs\session_*

"@ -ForegroundColor Cyan
pause
