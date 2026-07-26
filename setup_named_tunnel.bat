@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM ---------------------------------------------------------------------------
REM  setup_named_tunnel.bat
REM  Links this PC to your Cloudflare account and creates a named tunnel
REM  for the Streamlit + OAK dashboard (stable hostname).
REM ---------------------------------------------------------------------------

set "TUNNEL_NAME=kiif-oak-streamlit"
set "PORT=8501"
set "CF_DIR=%USERPROFILE%\.cloudflared"
set "CFG=%~dp0cloudflared.yml"

echo.
echo === Cloudflare named tunnel setup ===
echo Dashboard (your account):
echo   https://dash.cloudflare.com/f2ed2ffed361450d643350ed475ae9b1/home
echo Tunnel name: %TUNNEL_NAME%
echo Local app:   http://127.0.0.1:%PORT%
echo.

where cloudflared >nul 2>&1
if errorlevel 1 (
    echo [ERROR] cloudflared missing. Run install_remote_tunnel.bat first.
    pause
    exit /b 1
)

if not exist "%CF_DIR%\cert.pem" (
    echo [1/4] Login — a browser window will open.
    echo       Choose the Cloudflare account / zone you want to use, then Authorize.
    echo.
    cloudflared tunnel login
    if errorlevel 1 (
        echo [ERROR] Login failed.
        pause
        exit /b 1
    )
) else (
    echo [1/4] Already logged in: %CF_DIR%\cert.pem
)

echo.
echo [2/4] Create tunnel "%TUNNEL_NAME%" if missing...
cloudflared tunnel list 2>nul | findstr /I /C:"%TUNNEL_NAME%" >nul
if errorlevel 1 (
    cloudflared tunnel create %TUNNEL_NAME%
    if errorlevel 1 (
        echo [ERROR] Could not create tunnel.
        pause
        exit /b 1
    )
) else (
    echo Tunnel already exists.
)

echo.
echo [3/4] Writing %CFG% ...
for /f "tokens=1" %%I in ('cloudflared tunnel list ^| findstr /I /C:"%TUNNEL_NAME%"') do set "TUNNEL_ID=%%I"
if not defined TUNNEL_ID (
    echo [ERROR] Could not read tunnel UUID. Run: cloudflared tunnel list
    pause
    exit /b 1
)

(
echo # Auto-generated for KIIF OAK Streamlit remote access
echo tunnel: %TUNNEL_ID%
echo credentials-file: %CF_DIR%\%TUNNEL_ID%.json
echo.
echo ingress:
echo   - hostname: PLACEHOLDER.YOUR_DOMAIN.com
echo     service: http://127.0.0.1:%PORT%
echo   - service: http_status:404
) > "%CFG%"

echo Wrote config with tunnel id %TUNNEL_ID%
echo.
echo [4/4] DNS route — pick a hostname on a domain in THIS Cloudflare account.
echo.
echo Example (replace oak.example.com with your subdomain):
echo   cloudflared tunnel route dns %TUNNEL_NAME% oak.example.com
echo.
echo Then edit cloudflared.yml and set:
echo   hostname: oak.example.com
echo.
echo After that, use:  run_remote_named.bat
echo.
echo In the dashboard you can also manage tunnels under:
echo   Zero Trust ^> Networks ^> Tunnels
echo   https://one.dash.cloudflare.com/
echo.
cloudflared tunnel list
pause
