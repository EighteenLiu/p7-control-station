param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$distribution = 'Ubuntu-24.04'

function Get-Devices {
    $json = & usbipd.exe state
    if ($LASTEXITCODE -ne 0) { throw '无法读取 usbipd 设备状态。' }
    $state = $json | ConvertFrom-Json
    $connected = @($state.Devices | Where-Object { $_.BusId })
    $pcan = @($connected | Where-Object { $_.InstanceId -match '(?i)VID_0C72&PID_000C' })
    $cameras = @($connected | Where-Object { $_.InstanceId -match '(?i)VID_2BC5&PID_(0670|0804)' })
    if ($pcan.Count -ne 4 -or $cameras.Count -ne 3) {
        throw "需要 4 个 PCAN 和 3 个 Orbbec 相机，当前发现 $($pcan.Count) 个 PCAN、$($cameras.Count) 个相机。请检查连接或多余设备。"
    }
    return @($pcan + $cameras)
}

try {
    $usbipdDefault = Join-Path $env:ProgramFiles 'usbipd-win'
    if (Test-Path -LiteralPath (Join-Path $usbipdDefault 'usbipd.exe')) {
        $env:Path = $usbipdDefault + ';' + $env:Path
    }
    if (-not (Get-Command usbipd.exe -ErrorAction SilentlyContinue)) {
        throw '未找到 usbipd，请先安装 usbipd-win。'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot '20261109_start_p7.sh'))) {
        throw '未找到 WSL 启动脚本，请将此脚本放回项目文件夹。'
    }
    $devices = @(Get-Devices)
    foreach ($device in $devices) {
        $status = if ($device.ClientIPAddress) { '已连接' } elseif ($device.PersistedGuid) { '已共享' } else { '未共享' }
        Write-Host "$($device.BusId)  $($device.Description)  $status"
    }
    if ($CheckOnly) { Write-Host '检查完成，未修改设备状态。'; exit 0 }
    & wsl.exe -d $distribution -- true
    if ($LASTEXITCODE -ne 0) { throw "无法启动 WSL 发行版 $distribution。" }
    foreach ($device in $devices) {
        if (-not $device.PersistedGuid) {
            Write-Host "共享 $($device.BusId)：Windows 可能请求管理员授权。"
            $process = Start-Process -FilePath 'usbipd.exe' -ArgumentList @('bind', '--busid', $device.BusId) -Verb RunAs -Wait -PassThru
            if ($process.ExitCode -ne 0) { throw "共享 $($device.BusId) 失败，退出码 $($process.ExitCode)。" }
        }
    }
    # Refresh after binding; USB identifiers can change during re-enumeration.
    $devices = @(Get-Devices)
    foreach ($device in $devices) {
        if ($device.ClientIPAddress) {
            Write-Host "$($device.BusId) 已连接，跳过。"
            continue
        }
        Write-Host "连接 $($device.BusId) 到 WSL..."
        & usbipd.exe attach --wsl $distribution --busid $device.BusId
        if ($LASTEXITCODE -ne 0) { throw "连接 $($device.BusId) 失败。" }
    }
    $devices = @(Get-Devices)
    if (@($devices | Where-Object { -not $_.ClientIPAddress }).Count -ne 0) {
        throw '有设备未成功连接，请运行 usbipd list 检查。'
    }
    Write-Host 'USB 已连接，正在启动控制站。若提示 sudo 密码，请输入 Ubuntu 密码。'
    $quotedDirectory = '"' + $PSScriptRoot + '"'
    & wsl.exe -d $distribution --cd $quotedDirectory -- bash ./20261109_start_p7.sh
    if ($LASTEXITCODE -ne 0) { throw "控制站退出，退出码 $LASTEXITCODE。" }
} catch {
    Write-Host "启动失败：$_" -ForegroundColor Red
    exit 1
}
