@echo off
setlocal
if not exist "D:\" (
  echo D drive not found.
  pause
  exit /b 1
)
if not exist "D:\20261109_p7_setup" mkdir "D:\20261109_p7_setup"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/EighteenLiu/p7-control-station/main/20261109_bootstrap.ps1' -OutFile 'D:\20261109_p7_setup\20261109_bootstrap.ps1'"
if errorlevel 1 (
  echo Download failed. Check network and repository access.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\20261109_p7_setup\20261109_bootstrap.ps1"
pause
