@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM ---------------------------------------------------------------------------
REM  build.bat  - Build the VIO Docker image on Windows
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
    goto do_build
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

:do_build
echo.
echo Building VIO Docker image first build can take 30-90+ minutes...
echo.
docker compose build
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. See output above.
    pause
    exit /b 1
)
echo.
echo Build complete.
pause
