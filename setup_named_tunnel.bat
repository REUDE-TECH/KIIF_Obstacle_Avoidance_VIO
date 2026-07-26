@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM Named Cloudflare tunnel: REUDETECH -> reudetech.reude.tech

set "TUNNEL_NAME=REUDETECH"
set "HOSTNAME=reudetech.reude.tech"
set "PORT=8501"
set "CF_DIR=%USERPROFILE%\.cloudflared"
set "CFG=%~dp0cloudflared.yml"

echo.
echo === Cloudflare named tunnel setup ===
echo Dashboard: https://dash.cloudflare.com/f2ed2ffed361450d643350ed475ae9b1/home
echo Tunnel:    %TUNNEL_NAME%
echo Hostname:  %HOSTNAME%
echo Local:     http://127.0.0.1:%PORT%
echo.

where cloudflared >nul 2>&1
if errorlevel 1 (
    echo [ERROR] cloudflared missing. Run install_remote_tunnel.bat first.
    pause
    exit /b 1
)

if not exist "%CF_DIR%\cert.pem" (
    echo [1/5] Browser login — Authorize your Cloudflare account/zone.
    cloudflared tunnel login
    if errorlevel 1 (
        echo [ERROR] Login failed.
        pause
        exit /b 1
    )
) else (
    echo [1/5] Already logged in.
)

echo.
echo [2/5] Create tunnel %TUNNEL_NAME% if needed...
cloudflared tunnel list 2>nul | findstr /I /C:"%TUNNEL_NAME%" >nul
if errorlevel 1 (
    cloudflared tunnel create %TUNNEL_NAME%
    if errorlevel 1 (
        echo [ERROR] tunnel create failed.
        pause
        exit /b 1
    )
) else (
    echo Tunnel exists.
)

set "TUNNEL_ID="
for /f "tokens=1" %%I in ('cloudflared tunnel list ^| findstr /I /C:"%TUNNEL_NAME%"') do set "TUNNEL_ID=%%I"
if not defined TUNNEL_ID (
    echo [ERROR] Could not read tunnel UUID.
    cloudflared tunnel list
    pause
    exit /b 1
)
echo Tunnel ID: %TUNNEL_ID%

echo.
echo [3/5] DNS route %HOSTNAME% ...
cloudflared tunnel route dns %TUNNEL_NAME% %HOSTNAME%
if errorlevel 1 (
    echo [WARN] DNS route failed. Is reude.tech in this Cloudflare account?
    echo        Add the domain in the dashboard, or change HOSTNAME in this script.
)

echo.
echo [4/5] Writing %CFG% ...
(
echo # KIIF OAK Streamlit — named tunnel REUDETECH
echo tunnel: %TUNNEL_ID%
echo credentials-file: %CF_DIR%\%TUNNEL_ID%.json
echo.
echo ingress:
echo   - hostname: %HOSTNAME%
echo     service: http://127.0.0.1:%PORT%
echo   - service: http_status:404
) > "%CFG%"
echo Wrote %CFG%

echo.
echo [5/5] Done. Next: run_remote_named.bat
echo Remote URL: https://%HOSTNAME%
echo.
cloudflared tunnel list
pause
