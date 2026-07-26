@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM  stop.bat  —  Double-click this to stop all VIO containers on Windows
REM ─────────────────────────────────────────────────────────────────────────────
cd /d "%~dp0.."
call "%~dp0_env.bat"
if errorlevel 1 (
    pause
    exit /b 1
)
echo Stopping VIO containers...
docker compose down
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Failed to stop containers. See output above.
    pause
    exit /b %ERRORLEVEL%
)
echo Containers stopped.
pause
