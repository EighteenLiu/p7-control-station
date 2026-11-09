"""Query P7 V1 motor handshakes and O6 hand angles without motion commands."""

import select
import socket
import struct
import time
from pathlib import Path

FRAME = struct.Struct("=IB3x8s")
ROLES = {
    "左臂": tuple(range(61, 68)),
    "右臂": tuple(range(51, 58)),
    "左手": (0x28,),
    "右手": (0x27,),
}


def probe(interface, wrist_modes=None):
    channel = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
    channel.bind((interface,))
    responses = set()
    try:
        for motor_id in (0x27, 0x28, *range(51, 58), *range(61, 68)):
            wrist = motor_id in (56, 57, 66, 67)
            request_id = motor_id + 0x600 if wrist else motor_id
            request = bytes((0x67, 0x0B, 0, 0, 0, 0, 0x04, 0x76)) if wrist else b"\x01"
            channel.send(FRAME.pack(request_id, len(request), request))
            end = time.monotonic() + 0.12
            while time.monotonic() < end:
                readable, _, _ = select.select([channel], [], [], end - time.monotonic())
                if not readable:
                    break
                can_id, size, data = FRAME.unpack(channel.recv(FRAME.size))
                if can_id != request_id:
                    continue
                if wrist and size == 8 and data[0] == motor_id and data[1] == 0x0B:
                    responses.add(motor_id)
                    if wrist_modes is not None:
                        wrist_modes[motor_id] = struct.unpack('<i', data[2:6])[0]
                elif not wrist and data[0] == 1 and ((motor_id in (0x27, 0x28) and size == 7) or (motor_id not in (0x27, 0x28) and size >= 2)):
                    responses.add(motor_id)
    finally:
        channel.close()
    return responses


def main():
    paths = sorted(Path('/sys/class/net').glob('can*'))
    if not paths:
        raise SystemExit('未找到 CAN 接口')
    for path in paths:
        try:
            modes = {}
            responses = probe(path.name, modes)
        except OSError as error:
            print(f'{path.name}: 查询失败：{error}')
            continue
        found = []
        for role, expected in ROLES.items():
            matched = [value for value in expected if value in responses]
            if matched:
                found.append(f'{role}: {len(matched)}/{len(expected)} ({matched})')
        print(f"{path.name}: " + ('；'.join(found) if found else '没有收到已识别的只读响应'))
        if modes:
            print('  腕部控制模式只读值：' + ', '.join(f'{motor}={mode}' for motor, mode in sorted(modes.items())))
    print('腕部 V2 使用只读模式寄存器查询；物理左右对应关系仍需现场确认。')


if __name__ == '__main__':
    main()
