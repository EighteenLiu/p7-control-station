$ErrorActionPreference = 'Stop'
$destination = 'D:\20261109_p7-control-station'
$stagingRoot = 'D:\20261109_p7_setup'
try {
    if (-not (Test-Path -LiteralPath 'D:\')) { throw '未找到 D 盘。' }
    if (Test-Path -LiteralPath $destination) {
        if (-not (Test-Path -LiteralPath (Join-Path $destination '.bootstrap-origin'))) {
            throw "目录 $destination 已存在且不是本安装器创建的目录；为避免覆盖，已停止。"
        }
        Write-Host '已发现之前下载的项目。下载最新安装脚本，保留控制代码和配置。'
        $backup = Join-Path $stagingRoot ([guid]::NewGuid().ToString())
        New-Item -ItemType Directory -Path $backup -Force | Out-Null
        foreach ($name in @('20261109_new_pc_setup.ps1','20261109_new_pc_setup.sh','20261109_install_ros2.sh','20261109_start_p7_windows.ps1')) {
            $target = Join-Path $destination $name
            $download = Join-Path $backup ($name + '.new')
            Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/EighteenLiu/p7-control-station/main/$name" -OutFile $download
            if ((Get-Item -LiteralPath $download).Length -eq 0) { throw "下载 $name 为空，已停止。" }
            if (Test-Path -LiteralPath $target) { Copy-Item -LiteralPath $target -Destination (Join-Path $backup $name) }
            Copy-Item -LiteralPath $download -Destination $target -Force
        }
    } else {
        $staging = Join-Path $stagingRoot ([guid]::NewGuid().ToString())
        New-Item -ItemType Directory -Path $staging -Force | Out-Null
        $archive = Join-Path $staging 'source.zip'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Write-Host '正在从 GitHub 下载控制站...'
        Invoke-WebRequest -UseBasicParsing 'https://github.com/EighteenLiu/p7-control-station/archive/refs/heads/main.zip' -OutFile $archive
        Expand-Archive -LiteralPath $archive -DestinationPath $staging
        $source = Join-Path $staging 'p7-control-station-main'
        if (-not (Test-Path -LiteralPath (Join-Path $source '20261109_new_pc_setup.ps1'))) {
            throw '下载内容不完整，请检查仓库版本。'
        }
        New-Item -ItemType File -Path (Join-Path $source '.bootstrap-origin') | Out-Null
        Move-Item -LiteralPath $source -Destination $destination
    }
    Write-Host '即将启动安装器，Windows 会请求管理员权限。'
    & (Join-Path $destination '20261109_new_pc_setup.ps1')
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} catch {
    Write-Host "下载或安装失败：$_" -ForegroundColor Red
    exit 1
}
