@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM ---------------------------------------------------------------------------
REM  setup_named_tunnel.bat
REM  Requires a REAL domain already in your Cloudflare account.
REM  If you see "invalid domain", use run_remote.bat instead (no domain needed).
REM ---------------------------------------------------------------------------

if "%~1"=="" (
  echo.
  echo Usage:
  echo   setup_named_tunnel.bat  YOUR_DOMAIN.com  [subdomain]
  echo.
  echo Example:
  echo   setup_named_tunnel.bat example.com oak
  echo     -^> hostname oak.example.com
  echo.
  echo If you do NOT have a domain in Cloudflare, use:
  echo   run_remote.bat
  echo.
  pause
  exit /b 1
)

set "DOMAIN=%~1"
set "SUB=%~2"
if "%SUB%"=="" set "SUB=reudetech"
set "HOSTNAME=%SUB%.%DOMAIN%"
set "TUNNEL_NAME=REUDETECH"
set "PORT=8501"
set "CF_DIR=%USERPROFILE%\.cloudflared"
set "CFG=%~dp0cloudflared.yml"

echo.
echo === Cloudflare named tunnel ===
echo Tunnel:   %TUNNEL_NAME%
echo Hostname: %HOSTNAME%
echo Domain MUST already exist in Cloudflare or you get "invalid domain".
echo.

where cloudflared >nul 2>&1
if errorlevel 1 (
  echo [ERROR] cloudflared missing. Run install_remote_tunnel.bat
  pause
  exit /b 1
)

if not exist "%CF_DIR%\cert.pem" (
  echo [1/5] Browser login — select domain "%DOMAIN%" then Authorize.
  cloudflared tunnel login
  if errorlevel 1 (
    echo [ERROR] Login failed / invalid domain.
    echo Add %DOMAIN% to Cloudflare first, or use run_remote.bat
    pause
    exit /b 1
  )
) else (
  echo [1/5] Already logged in.
)

echo [2/5] Create tunnel %TUNNEL_NAME%...
cloudflared tunnel list 2>nul | findstr /I /C:"%TUNNEL_NAME%" >nul
if errorlevel 1 (
  cloudflared tunnel create %TUNNEL_NAME%
  if errorlevel 1 ( echo [ERROR] create failed & pause & exit /b 1 )
) else ( echo Tunnel exists. )

set "TUNNEL_ID="
for /f "tokens=1" %%I in ('cloudflared tunnel list ^| findstr /I /C:"%TUNNEL_NAME%"') do set "TUNNEL_ID=%%I"
if not defined TUNNEL_ID ( echo [ERROR] no tunnel id & pause & exit /b 1 )

echo [3/5] DNS route %HOSTNAME%...
cloudflared tunnel route dns %TUNNEL_NAME% %HOSTNAME%
if errorlevel 1 (
  echo [ERROR] DNS route failed — invalid / missing domain %DOMAIN%
  echo Fix: Cloudflare Dashboard -^> Add site %DOMAIN%  OR  use run_remote.bat
  pause
  exit /b 1
)

echo [4/5] Writing %CFG%...
(
echo tunnel: %TUNNEL_ID%
echo credentials-file: %CF_DIR%\%TUNNEL_ID%.json
echo.
echo ingress:
echo   - hostname: %HOSTNAME%
echo     service: http://127.0.0.1:%PORT%
echo   - service: http_status:404
) > "%CFG%"

echo [5/5] Done. Run: run_remote_named.bat
echo URL: https://%HOSTNAME%
pause
