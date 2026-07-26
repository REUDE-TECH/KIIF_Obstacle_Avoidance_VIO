@echo off
REM Follow one container's logs (used by run.bat log windows).
REM Usage: _docker_logs.bat <container_name>
cd /d "%~dp0.."
call "%~dp0_env.bat"
if errorlevel 1 (
    pause
    exit /b 1
)
if "%~1"=="" (
    echo Usage: %~nx0 ^<container_name^>
    pause
    exit /b 1
)
echo Following logs for %~1  (Ctrl+C to close this window^)
docker logs -f "%~1"
pause
