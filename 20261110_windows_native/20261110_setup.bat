@echo off
cd /d "%~dp0"
set "PATH=D:\20261110_Python312;D:\20261110_Python312\Scripts;D:\20261110_Git\cmd;%ProgramFiles%\Git\cmd;%PATH%"
set "TEMP=D:\20261110_p7_download"
set "TMP=D:\20261110_p7_download"
if not exist "%TEMP%" mkdir "%TEMP%"
if not exist ".venv\Scripts\python.exe" (
  if exist "D:\20261110_Python312\python.exe" (
    "D:\20261110_Python312\python.exe" -m venv .venv
  ) else (
    py -3.12-64 -m venv .venv
  )
  if errorlevel 1 goto fail
)
".venv\Scripts\python.exe" -m pip install "python-can==4.6.1" "Pillow==13.0.0" "opencv-python-headless==5.0.0.93" "git+https://github.com/linker-bot/linkerbot-python-sdk.git@927290b8e27f9e2df3cc5b0a0776c36e2fb5175e"
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -c "import tkinter,can,cv2,PIL; from linkerbot import O6; print('Dependencies OK')"
if errorlevel 1 goto fail
echo Setup complete. PEAK PCAN driver and PCAN-Basic must be installed separately.
pause
exit /b 0
:fail
echo Setup failed. Install 64-bit Python 3.12 and Git, then check the error above.
pause
exit /b 1
