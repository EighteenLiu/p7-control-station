$ErrorActionPreference = 'Stop'
$distro = 'Ubuntu-24.04'
$project = $PSScriptRoot
try {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host '请在弹出的窗口中允许管理员权限。'
        Start-Process powershell.exe -Verb RunAs -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'))
        exit
    }
    if (-not (Test-Path -LiteralPath (Join-Path $project '20261109_p7_control_station.py'))) {
        throw '请先将此安装脚本放在完整项目文件夹中，再双击运行。'
    }
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw '未找到 winget。请先从 Microsoft Store 更新“应用安装程序”，然后重新运行。'
    }
    Write-Host '检查 Windows 虚拟化组件...'
    $restartNeeded = $false
    foreach ($feature in @('Microsoft-Windows-Subsystem-Linux', 'VirtualMachinePlatform')) {
        $state = (Get-WindowsOptionalFeature -Online -FeatureName $feature).State
        if ($state -ne 'Enabled') {
            Enable-WindowsOptionalFeature -Online -FeatureName $feature -All -NoRestart | Out-Null
            $restartNeeded = $true
        }
    }
    if ($restartNeeded) {
        Write-Host 'Windows 组件已启用。请手动重启电脑，重启后再次双击本安装脚本。' -ForegroundColor Yellow
        exit 0
    }
    Write-Host '安装或更新 WSL...'
    & wsl.exe --version
    if ($LASTEXITCODE -ne 0) {
        & wsl.exe --install --no-distribution
        if ($LASTEXITCODE -ne 0) {
            throw 'WSL 安装未完成。请检查输出；如提示需要重启，请重启后再次运行。'
        }
    }
    & wsl.exe --update
    if ($LASTEXITCODE -ne 0) { throw 'WSL 更新失败，请检查网络后重试。' }
    & wsl.exe --set-default-version 2
    if ($LASTEXITCODE -ne 0) { throw '设置 WSL 2 失败，请检查虚拟化是否启用。' }
    Write-Host '安装 USBIPD-WIN...'
    & winget.exe install --id dorssel.usbipd-win --exact --source winget --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) {
        throw "USBIPD 安装失败，退出码 $LASTEXITCODE。请查看上方输出。"
    }
    $installed = (& wsl.exe --list --quiet | Out-String) -replace [char]0, ''
    if ($installed -notmatch '(?m)^\s*Ubuntu-24\.04\s*$') {
        Write-Host '安装 Ubuntu 24.04。首次启动时请按提示创建 Linux 用户名和密码。'
        & wsl.exe --install -d $distro
        if ($LASTEXITCODE -ne 0) {
            throw 'Ubuntu 安装未完成。若提示重启，请重启后再次运行；否则检查网络。'
        }
    }
    Write-Host '准备 Ubuntu。首次运行如有提示，请先创建用户名和密码。'
    & wsl.exe -d $distro -- true
    if ($LASTEXITCODE -ne 0) { throw 'Ubuntu 未初始化，请从开始菜单打开 Ubuntu 24.04 完成初始化后重试。' }
    Write-Host '安装 Ubuntu 系统依赖（需要网络）...'
    & wsl.exe -d $distro -u root -- bash -c 'apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y git curl ca-certificates python3-venv python3-tk python3-pip iproute2 can-utils v4l-utils xfonts-wqy fonts-wqy-microhei libgl1 libglib2.0-0 libgomp1'
    if ($LASTEXITCODE -ne 0) { throw 'Ubuntu 系统依赖安装失败，请查看上方输出并重试。' }
    $quoted = '"' + $project + '"'
    Write-Host '安装 ROS 2 Jazzy（首次下载可能较久）...'
    & wsl.exe -d $distro -u root --cd $quoted -- bash ./20261109_install_ros2.sh
    if ($LASTEXITCODE -ne 0) { throw 'ROS 2 安装失败，请查看上方输出并重试。' }
    Write-Host '创建项目 Python 环境并下载安装 SDK...'
    & wsl.exe -d $distro --cd $quoted -- bash ./20261109_new_pc_setup.sh
    if ($LASTEXITCODE -ne 0) { throw 'Python 环境安装失败，请查看上方输出并重试。' }
    & wsl.exe -d $distro -- bash -c 'grep -Fqx "source /opt/ros/jazzy/setup.bash" ~/.bashrc || printf "\\nsource /opt/ros/jazzy/setup.bash\\n" >> ~/.bashrc'
    if ($LASTEXITCODE -ne 0) { throw '配置 ROS 2 环境失败。' }
    Write-Host '检查 PCAN 内核模块...'
    & wsl.exe -d $distro -- bash -c 'modinfo peak_usb >/dev/null 2>&1'
    if ($LASTEXITCODE -ne 0) {
        Write-Host '未找到 peak_usb 模块：安装尚不能用于 PCAN，请联系我提供该电脑的 WSL 内核信息。' -ForegroundColor Yellow
        exit 2
    }
    Write-Host '基础环境安装完成。重新打开本文件夹后双击 20261109_start_p7_windows.bat 启动。' -ForegroundColor Green
    Write-Host '请现场验证 USB、三路画面、左右设备和急停；本脚本未执行机械臂运动测试。'
} catch {
    Write-Host "安装未完成：$_" -ForegroundColor Red
    exit 1
} finally {
    Read-Host '按回车关闭窗口'
}
