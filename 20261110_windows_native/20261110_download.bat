@echo off
setlocal
if not exist "D:\" (
  echo D drive not found.
  pause
  exit /b 1
)
set "DEST=D:\20261110_p7_windows"
if exist "%DEST%" (
  echo Target folder already exists: %DEST%
  echo Open it and run 20261110_setup.bat; no files were overwritten.
  pause
  exit /b 1
)
mkdir "D:\20261110_p7_download"
set "TEMP=D:\20261110_p7_download"
set "TMP=D:\20261110_p7_download"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $p='D:\20261110_p7_download'; $id=[guid]::NewGuid().ToString(); $s=Join-Path $p $id; New-Item -ItemType Directory -Path $s | Out-Null; $z=Join-Path $s 'source.zip'; Invoke-WebRequest -UseBasicParsing 'https://github.com/EighteenLiu/p7-control-station/archive/refs/heads/main.zip' -OutFile $z; Expand-Archive -LiteralPath $z -DestinationPath $s; $src=Join-Path $s 'p7-control-station-main\20261110_windows_native'; if (!(Test-Path (Join-Path $src '20261110_setup.bat'))) { throw 'Windows files not found in repository' }; Move-Item -LiteralPath $src -Destination 'D:\20261110_p7_windows'"
if errorlevel 1 (
  echo Download failed. Check network and repository access.
  pause
  exit /b 1
)
call "%DEST%\20261110_setup.bat"
