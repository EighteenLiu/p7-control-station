#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export PYTHONDONTWRITEBYTECODE=1
export PIP_NO_CACHE_DIR=1
mkdir -p 20261109_p7_temp
export TMPDIR="$PWD/20261109_p7_temp"
if [[ -e 20261109_p7_env ]]; then
    if [[ ! -f 20261109_p7_env/.new_pc_setup ]]; then
        echo '检测到已有环境，为避免覆盖，请先改名或移走 20261109_p7_env 后重试。' >&2
        exit 1
    fi
else
    python3 -m venv 20261109_p7_env
    touch 20261109_p7_env/.new_pc_setup
fi
./20261109_p7_env/bin/python -m pip install --upgrade pip
./20261109_p7_env/bin/python -m pip install 'git+https://github.com/linker-bot/linkerbot-python-sdk.git@927290b8e27f9e2df3cc5b0a0776c36e2fb5175e' 'pin==4.1.0' 'python-can==4.6.1' 'Pillow==13.0.0' 'opencv-python-headless==5.0.0.93'
./20261109_p7_env/bin/python -c 'import tkinter, can, cv2, PIL, pinocchio, linkerbot; print("Python 依赖导入成功")'
