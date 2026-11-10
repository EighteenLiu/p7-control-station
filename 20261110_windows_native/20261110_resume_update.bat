@echo off
setlocal
set "DEST=D:\20261110_p7_windows"
if not exist "%DEST%\20261109_p7_control_station.py" (
  echo Existing Windows project was not found at %DEST%.
  echo Use 20261110_download.bat for a first installation.
  pause
  exit /b 1
)
echo Downloading updated installer scripts; project code and configuration will be kept.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $d='D:\20261110_p7_windows'; $b=Join-Path 'D:\20261110_p7_download' ([guid]::NewGuid().ToString()); New-Item -ItemType Directory -Path $b -Force | Out-Null; $files=@('20261110_prerequisites.ps1','20261110_prerequisites.bat','20261110_setup.bat'); foreach($f in $files){$n=Join-Path $b ($f+'.new'); Write-Host ('Downloading '+$f); Invoke-WebRequest -UseBasicParsing -TimeoutSec 60 ('https://raw.githubusercontent.com/EighteenLiu/p7-control-station/main/20261110_windows_native/'+$f) -OutFile $n; if((Get-Item $n).Length -eq 0){throw 'Empty download'}}; foreach($f in $files){$target=Join-Path $d $f; if(Test-Path -LiteralPath $target){Copy-Item -LiteralPath $target -Destination (Join-Path $b $f)}; Copy-Item -LiteralPath (Join-Path $b ($f+'.new')) -Destination $target -Force}; Write-Host ('Previous scripts backed up to '+$b)"
if errorlevel 1 (
  echo Update failed. Check network access.
  pause
  exit /b 1
)
call "%DEST%\20261110_prerequisites.bat"
