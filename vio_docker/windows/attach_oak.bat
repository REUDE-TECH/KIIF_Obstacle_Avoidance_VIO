@echo off
REM Elevate and run attach_oak.ps1 (UAC prompt expected)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%~dp0attach_oak.ps1""'"
