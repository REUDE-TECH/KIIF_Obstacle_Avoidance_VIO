@echo off
set "SRC=%~dp0"
set "DST=Z:\Engineering Team\10.1 Obstacle avoidance\camera_check\oa_pipeline"
echo Copying revised pipeline to:
echo   %DST%
if not exist "Z:\Engineering Team" (
  echo [ERROR] Z: drive not available. Reconnect the network drive first.
  pause
  exit /b 1
)
mkdir "%DST%" 2>nul
xcopy /E /I /Y "%SRC%*" "%DST%\"
echo.
echo Done. Run: %DST%\run.bat
pause
