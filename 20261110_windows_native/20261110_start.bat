@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run 20261110_setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -B 20261109_p7_control_station.py
pause
