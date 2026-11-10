$ErrorActionPreference = 'Stop'
$work = 'D:\20261110_p7_download\prerequisites'
try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Start-Process powershell.exe -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + $PSCommandPath + '"'))
        exit
    }
    if (-not [Environment]::Is64BitOperatingSystem) { throw '需要 64 位 Windows。' }
    New-Item -ItemType Directory -Force -Path $work | Out-Null
    $env:TEMP = $work
    $env:TMP = $work
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    function Assert-Signed($path, $subject) {
        $sig = Get-AuthenticodeSignature -LiteralPath $path
        if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch $subject) {
            throw "签名检查失败：$path；状态：$($sig.Status)"
        }
    }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    $pythonOk = $false
    if ($py) {
        $previousPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $process = Start-Process -FilePath $py.Source -ArgumentList @('-3.12','-c','"import struct,sys;sys.exit(0 if struct.calcsize(''P'')==8 else 1)"') -WindowStyle Hidden -Wait -PassThru
            $pythonOk = $process.ExitCode -eq 0
        } finally {
            $ErrorActionPreference = $previousPreference
        }
    }
    if (-not $pythonOk) {
        Write-Host '下载并安装 Python 3.12...'
        $installer = Join-Path $work 'python-3.12.10-amd64.exe'
        Invoke-WebRequest -UseBasicParsing 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $installer
        Assert-Signed $installer 'Python Software Foundation'
        $p = Start-Process -FilePath $installer -ArgumentList @('/passive','InstallAllUsers=1','PrependPath=1','Include_launcher=1','Include_pip=1','TargetDir=D:\20261110_Python312') -Wait -PassThru
        if ($p.ExitCode -ne 0) { throw "Python 安装退出码：$($p.ExitCode)" }
    }
    $env:Path = 'D:\20261110_Python312;D:\20261110_Python312\Scripts;' + $env:ProgramFiles + '\Git\cmd;' + $env:Path
    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
        Write-Host '从 Git for Windows 官方发布页下载 Git...'
        $release = Invoke-RestMethod -Headers @{'User-Agent'='P7-Installer'} 'https://api.github.com/repos/git-for-windows/git/releases/latest'
        $asset = @($release.assets | Where-Object { $_.name -match '^Git-.*-64-bit\.exe$' })
        if ($asset.Count -ne 1) { throw '无法确定 Git 官方安装包。' }
        $installer = Join-Path $work 'git-setup.exe'
        Invoke-WebRequest -UseBasicParsing $asset[0].browser_download_url -OutFile $installer
        Assert-Signed $installer 'Git for Windows|Johannes Schindelin'
        $p = Start-Process -FilePath $installer -ArgumentList @('/VERYSILENT','/NORESTART','/DIR=D:\20261110_Git') -Wait -PassThru
        if ($p.ExitCode -ne 0) { throw "Git 安装退出码：$($p.ExitCode)" }
    }
    $env:Path = 'D:\20261110_Git\cmd;' + $env:Path
    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) { throw '未找到 Git，请检查安装结果。' }
    Write-Host '下载 PEAK 官方驱动和 PCAN-Basic...'
    $driverZip = Join-Path $work 'peak-driver.zip'
    $basicZip = Join-Path $work 'pcan-basic.zip'
    Invoke-WebRequest -UseBasicParsing 'https://www.peak-system.com/quick/DrvSetup' -OutFile $driverZip
    Invoke-WebRequest -UseBasicParsing 'https://www.peak-system.com/fileadmin/media/files/PCAN-Basic.zip' -OutFile $basicZip
    $driverDir = Join-Path $work 'driver'
    $basicDir = Join-Path $work 'basic'
    Expand-Archive -LiteralPath $driverZip -DestinationPath $driverDir -Force
    Expand-Archive -LiteralPath $basicZip -DestinationPath $basicDir -Force
    $driver = Join-Path $driverDir 'PeakOemDrv.exe'
    $dll = Join-Path $basicDir 'x64\PCANBasic.dll'
    Assert-Signed $driver 'PEAK.*System'
    Assert-Signed $dll 'PEAK.*System'
    Copy-Item -LiteralPath $dll -Destination (Join-Path $PSScriptRoot 'PCANBasic.dll') -Force
    Write-Host '即将打开 PEAK 驱动安装向导，请按照向导完成安装。'
    $p = Start-Process -FilePath $driver -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "PEAK 驱动安装程序退出码：$($p.ExitCode)。请确认已完成向导。" }
    Write-Host '前置安装程序已运行完成。请重新打开本目录，双击 20261110_setup.bat 安装 Python 依赖。'
    Write-Host '驱动可能要求重启；完成后用 20261110_probe.bat 检查设备。'
} catch {
    Write-Host "前置安装未完成：$_" -ForegroundColor Red
    exit 1
} finally {
    Read-Host '按回车关闭窗口'
}
