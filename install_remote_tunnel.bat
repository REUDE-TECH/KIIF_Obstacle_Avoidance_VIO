@echo off
setlocal
cd /d "%~dp0"
echo Installing Cloudflare Tunnel client (cloudflared)...
winget install -e --id Cloudflare.cloudflared --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo.
    echo winget install failed. Manual download:
    echo   https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
    pause
    exit /b 1
)
echo.
echo Done. Close and reopen any terminals, then run run_remote.bat
where cloudflared
pause
