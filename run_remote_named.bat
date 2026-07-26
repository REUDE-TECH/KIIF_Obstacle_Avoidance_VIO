@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM Named Cloudflare tunnel (stable hostname). Run setup_named_tunnel.bat first.

set "PORT=8501"
set "CFG=%~dp0cloudflared.yml"

if not exist "%CFG%" (
    echo [ERROR] cloudflared.yml missing. Run setup_named_tunnel.bat first.
    pause
    exit /b 1
)

findstr /C:"PLACEHOLDER.YOUR_DOMAIN.com" "%CFG%" >nul
if not errorlevel 1 (
    echo [ERROR] cloudflared.yml still has PLACEHOLDER.YOUR_DOMAIN.com
    echo   1. cloudflared tunnel route dns kiif-oak-streamlit ^<your-host^>
    echo   2. Edit cloudflared.yml hostname to match
    pause
    exit /b 1
)

echo Detach OAK from WSL if needed:  usbipd detach --busid ^<BUSID^>
echo.

echo Starting Streamlit...
start "KIIF Streamlit" cmd /k "cd /d ""%~dp0"" && py -m pip install -r requirements.txt -q && py -m streamlit run app.py --server.port %PORT% --server.address 0.0.0.0 --server.headless true --server.enableCORS false --server.enableXsrfProtection false"

echo Waiting for port %PORT%...
powershell -NoProfile -Command "for($i=0;$i -lt 60;$i++){ if(Test-NetConnection 127.0.0.1 -Port %PORT% -WarningAction SilentlyContinue -InformationLevel Quiet){ exit 0 }; Start-Sleep 1 }; exit 1"
if errorlevel 1 (
    echo [ERROR] Streamlit did not start.
    pause
    exit /b 1
)

echo [OK] Starting named tunnel with %CFG%
echo Keep this window open.
cloudflared tunnel --config "%CFG%" run
pause
