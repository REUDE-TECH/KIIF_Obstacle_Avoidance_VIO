@echo off
REM Shared env for VIO Windows scripts — put Docker CLI on PATH for this session.
set "DOCKER_BIN="
if exist "C:\Program Files\Docker\Docker\resources\bin\docker.exe" (
    set "DOCKER_BIN=C:\Program Files\Docker\Docker\resources\bin"
)
if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" (
    set "DOCKER_DESKTOP_EXE=C:\Program Files\Docker\Docker\Docker Desktop.exe"
) else (
    set "DOCKER_DESKTOP_EXE="
)
if defined DOCKER_BIN (
    set "PATH=%DOCKER_BIN%;%PATH%"
)
where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] docker.exe not found.
    echo Install Docker Desktop, then open a NEW terminal, or add this to PATH:
    echo   C:\Program Files\Docker\Docker\resources\bin
    exit /b 1
)
exit /b 0
