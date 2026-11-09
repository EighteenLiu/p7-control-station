#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
. /etc/os-release
if [[ "${ID:-}" != ubuntu || "${VERSION_CODENAME:-}" != noble || "$(dpkg --print-architecture)" != amd64 ]]; then
    echo 'ROS 2 安装仅支持 Ubuntu 24.04 amd64。' >&2
    exit 1
fi
export DEBIAN_FRONTEND=noninteractive
apt-get install -y software-properties-common
add-apt-repository -y universe
mkdir -p 20261109_p7_temp
version=$(curl -fsSL https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])')
[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo '无效的 ROS 软件源版本' >&2; exit 1; }
deb="$PWD/20261109_p7_temp/ros2-apt-source-${version}.deb"
curl -fL --retry 3 -o "$deb" "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${version}/ros2-apt-source_${version}.noble_all.deb"
apt-get install -y "$deb"
apt-get update
apt-get install -y ros-jazzy-ros-base python3-colcon-common-extensions
test -f /opt/ros/jazzy/setup.bash
echo 'ROS 2 Jazzy 已安装。'
