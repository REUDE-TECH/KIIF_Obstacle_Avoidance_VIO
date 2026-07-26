@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM ---------------------------------------------------------------------------
REM  run.bat  - Start VIO containers on Windows (camera + VINS)
REM ---------------------------------------------------------------------------
cd /d "%~dp0.."
call "%~dp0_env.bat"
if errorlevel 1 (
    pause
    exit /b 1
)

echo.
echo Checking Docker daemon...
docker info >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [OK] Docker is already ready - skipping restart.
    goto do_run
)

echo Docker not ready yet. Starting Docker Desktop...
if defined DOCKER_DESKTOP_EXE (
    echo Starting: %DOCKER_DESKTOP_EXE%
    start "" "%DOCKER_DESKTOP_EXE%"
) else (
    echo [WARNING] Could not locate Docker Desktop.exe. Start it manually.
)

echo Waiting for Docker daemon up to about 3 minutes...
set /a _tries=0
:wait_docker
set /a _tries+=1
docker info >nul 2>&1
if %ERRORLEVEL% equ 0 goto docker_ready
if !_tries! geq 90 (
    echo.
    echo [ERROR] Docker daemon did not become ready.
    echo   1. Open Docker Desktop and wait until Engine running.
    echo   2. Accept any first-run prompts.
    echo   3. Then re-run this script.
    echo.
    docker info
    pause
    exit /b 1
)
set /a _sec=!_tries!*2
echo   ... still waiting !_sec!s - keep Docker Desktop open
timeout /t 2 /nobreak >nul
goto wait_docker

:docker_ready
echo [OK] Docker daemon is ready.

:do_run
echo.
echo Preflight: OAK-D must be attached to docker-desktop via usbipd...

REM Prefer usbipd next to Program Files if not already on PATH
where usbipd >nul 2>&1
if not errorlevel 1 goto usbipd_found
if exist "%ProgramFiles%\usbipd-win\usbipd.exe" (
    set "PATH=%ProgramFiles%\usbipd-win;!PATH!"
)
where usbipd >nul 2>&1
if errorlevel 1 (
    echo [ERROR] usbipd-win is not installed.
    echo   Run windows\install_prereqs.bat then windows\attach_oak.bat
    pause
    exit /b 1
)

:usbipd_found
REM Accept "Attached" (in WSL). "Shared" alone is not enough - must attach.
usbipd list | findstr /I "Attached" >nul
if not errorlevel 1 goto oak_ok
echo [ERROR] OAK-D is not Attached to WSL right now.
echo   Current usbipd list:
usbipd list
echo.
echo   Fix: run windows\attach_oak.bat as Administrator, then re-run this script.
echo   Note: state must say Attached not only Shared or Not shared.
pause
exit /b 1

:oak_ok
echo [OK] usbipd reports Attached.

echo Verifying camera is visible inside docker-desktop WSL...
wsl -d docker-desktop -e lsusb 2>nul | findstr /I "03e7" >nul
if errorlevel 1 (
    echo [ERROR] usbipd says Attached, but docker-desktop does not see Movidius 03e7.
    echo   Fix:
    echo     1. Admin PowerShell:
    echo        usbipd detach --busid YOUR_BUSID
    echo        usbipd attach --wsl docker-desktop --busid YOUR_BUSID
    echo     2. Confirm:  wsl -d docker-desktop -e lsusb
    echo        must show 03e7 Movidius
    echo     3. Re-run this script
    wsl -d docker-desktop -e lsusb
    pause
    exit /b 1
)
echo [OK] Movidius device visible in docker-desktop.

if exist "outputs\current_session.txt" del "outputs\current_session.txt"

echo Creating outputs directory...
if not exist "outputs" mkdir "outputs"

echo.
echo Starting Docker containers: feature_tracker + vins_fusion
echo Note: mavlink_udp is optional - needs a flight-controller UART.
echo       PC testing skips it. Later: docker compose --profile fc up -d
docker compose up -d
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start containers. See output above.
    pause
    exit /b 1
)

timeout /t 2 /nobreak >nul

echo Opening terminals to follow logs...
start "feature_tracker logs" cmd /k ""%~dp0_docker_logs.bat" feature_tracker"
start "vins_fusion logs"     cmd /k ""%~dp0_docker_logs.bat" vins_fusion"

echo.
echo Containers started camera + VIO. mavlink_udp NOT started.
echo Outputs go under .\outputs\session_YYYYMMDD_HHMMSS\
echo.
choice /c s /n /m "Press s to STOP recording and shut down containers..."

echo.
echo Stopping VIO containers...
docker compose down
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to stop containers.
    pause
    exit /b 1
)
echo.
echo Containers stopped.
pause
