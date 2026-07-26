@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM ---------------------------------------------------------------------------
REM  run_remote.bat  - Local Streamlit + OAK camera, exposed via Cloudflare Tunnel
REM  Camera stays on THIS PC. Phone/laptop open the https://*.trycloudflare.com URL.
REM ---------------------------------------------------------------------------

echo.
echo === KIIF Obstacle Avoidance (remote access) ===
echo Camera must be on THIS Windows PC (not attached to WSL/Docker).
echo   If needed:  usbipd detach --busid ^<BUSID^>
echo.

where cloudflared >nul 2>&1
if errorlevel 1 (
    if exist "%LocalAppData%\cloudflared\cloudflared.exe" (
        set "PATH=%LocalAppData%\cloudflared;%PATH%"
    )
)
where cloudflared >nul 2>&1
if errorlevel 1 (
    echo [ERROR] cloudflared not found.
    echo   Run install_remote_tunnel.bat once, then re-run this script.
    pause
    exit /b 1
)

echo Installing / updating Python deps...
py -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)

set PORT=8501

echo.
echo Starting Streamlit on http://0.0.0.0:%PORT% ...
start "KIIF Streamlit" cmd /k "cd /d ""%~dp0"" && py -m streamlit run app.py --server.port %PORT% --server.address 0.0.0.0 --server.headless true --server.enableCORS false --server.enableXsrfProtection false"

echo Waiting for Streamlit to listen on port %PORT%...
set /a _tries=0
:wait_port
set /a _tries+=1
powershell -NoProfile -Command "exit (Test-NetConnection -ComputerName 127.0.0.1 -Port %PORT% -WarningAction SilentlyContinue -InformationLevel Quiet) -eq $false" >nul 2>&1
if %ERRORLEVEL% equ 0 goto port_ok
if %_tries% geq 60 (
    echo [ERROR] Streamlit did not open port %PORT%.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_port

:port_ok
echo [OK] Streamlit is up.
echo.
echo Starting Cloudflare quick tunnel...
echo Look for a line like:  https://xxxx.trycloudflare.com
echo Open that URL on your phone / remote laptop.
echo Keep BOTH windows open. Close this tunnel window to stop remote access.
echo.
cloudflared tunnel --url http://127.0.0.1:%PORT%
echo.
echo Tunnel stopped.
pause
