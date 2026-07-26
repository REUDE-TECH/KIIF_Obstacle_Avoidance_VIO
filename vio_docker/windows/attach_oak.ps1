#Requires -RunAsAdministrator
<#
.SYNOPSIS
  Bind + attach OAK-D into docker-desktop, with --auto-attach.

  DepthAI re-enumerates the Myriad during boot. A normal attach often drops
  (Shared again) and feature_tracker then dies with X_LINK_DEVICE_NOT_FOUND.
  --auto-attach keeps re-connecting; leave the auto-attach window open while VIO runs.
#>

$ErrorActionPreference = "Stop"

Write-Host "=== Attach OAK-D to docker-desktop (auto-attach) ===" -ForegroundColor Cyan

$usbipdExe = $null
foreach ($c in @(
        (Get-Command usbipd -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
        "$env:ProgramFiles\usbipd-win\usbipd.exe"
    )) {
    if ($c -and (Test-Path $c)) { $usbipdExe = $c; break }
}
if (-not $usbipdExe) {
    throw "usbipd not found. Run windows\install_prereqs.bat first."
}
$env:Path = "$(Split-Path $usbipdExe -Parent);$env:Path"

& $usbipdExe list

$lines = (& $usbipdExe list 2>&1 | Out-String) -split "`r?`n"
$candidates = @()
foreach ($line in $lines) {
    if ($line -match '(?i)luxonis|movidius|myriad|oak|depthai|03e7') {
        $candidates += $line
    }
}
if ($candidates.Count -eq 0) {
    Write-Host "[!] Plug OAK-D into USB3, wait 3s, re-run." -ForegroundColor Yellow
    pause
    exit 1
}

$busId = $null
if ($candidates[0] -match '^\s*([0-9]+-[0-9]+)') { $busId = $Matches[1] }
if (-not $busId) { throw "Could not parse BUSID from: $($candidates[0])" }
Write-Host "BUSID: $busId" -ForegroundColor Cyan

$dd = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if ((Test-Path $dd) -and -not (Get-Process "Docker Desktop" -ErrorAction SilentlyContinue)) {
    Start-Process $dd
    Start-Sleep -Seconds 10
}

Write-Host "[+] Detach any stale client..." -ForegroundColor Yellow
& $usbipdExe detach --busid $busId 2>$null
Start-Sleep -Seconds 1

Write-Host "[+] Bind..." -ForegroundColor Yellow
& $usbipdExe bind --busid $busId

# Start auto-attach in a separate window that MUST stay open during the VIO run.
$autoCmd = @"
`$env:Path = '$(Split-Path $usbipdExe -Parent);' + `$env:Path
Write-Host 'AUTO-ATTACH active for busid $busId -> docker-desktop' -ForegroundColor Green
Write-Host 'Keep this window OPEN while VIO / feature_tracker is running.' -ForegroundColor Yellow
Write-Host 'Close it only after you press s to stop run.bat.' -ForegroundColor Yellow
Write-Host ''
usbipd attach --wsl docker-desktop --auto-attach --busid $busId
Write-Host 'auto-attach exited.' -ForegroundColor Red
pause
"@
$autoPath = Join-Path $env:TEMP "usbipd_auto_attach_$busId.ps1"
Set-Content -Path $autoPath -Value $autoCmd -Encoding UTF8
Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$autoPath`""

Write-Host "[+] Waiting for device to appear in docker-desktop..." -ForegroundColor Yellow
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    $lsusb = & wsl -d docker-desktop -e lsusb 2>$null | Out-String
    if ($lsusb -match '03e7') {
        $ok = $true
        break
    }
}

Write-Host "`nusbipd list:" -ForegroundColor Yellow
& $usbipdExe list
Write-Host "`nlsusb (docker-desktop):" -ForegroundColor Yellow
& wsl -d docker-desktop -e lsusb

if (-not $ok) {
    Write-Host @"

[!] Movidius 03e7 not visible in docker-desktop yet.
    Check the AUTO-ATTACH window for errors.
    Try another USB3 port, then re-run this script.

"@ -ForegroundColor Red
    pause
    exit 1
}

Write-Host @"

[OK] Camera visible in docker-desktop (03e7).
Next:
  1. Leave the AUTO-ATTACH PowerShell window OPEN
  2. Camera Recorder tab = DISCONNECTED
  3. Run windows\run.bat
  4. feature_tracker must NOT say X_LINK_DEVICE_NOT_FOUND

"@ -ForegroundColor Green
pause
