#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export PYTHONDONTWRITEBYTECODE=1

if [[ ! -x ./20261109_p7_env/bin/python ]]; then
    echo '未找到 P7 环境：20261109_p7_env/bin/python' >&2
    exit 1
fi
for iface in can0 can1 can2 can3; do
    if [[ ! -e "/sys/class/net/$iface" ]]; then
        echo "未找到 $iface：请先在 Windows 中将 PCAN 转发到 WSL。" >&2
        exit 1
    fi
    details=$(ip -details link show "$iface")
    if [[ $details == *"<LISTEN-ONLY>"* ]]; then
        echo "$iface 处于只监听模式，请先关闭并重新配置正常 CAN 模式。" >&2
        exit 1
    fi
    if [[ $details != *"bitrate 1000000"* || $details != *"state ERROR-ACTIVE"* ]]; then
        if [[ $details == *",UP,"* ]]; then
            echo "$iface 已启动但参数不符合 1 Mbps / ERROR-ACTIVE，请检查后重试。" >&2
            exit 1
        fi
        sudo ip link set "$iface" type can bitrate 1000000
        sudo ip link set "$iface" up
    fi
done
exec ./20261109_p7_env/bin/python -B 20261109_p7_control_station.py
