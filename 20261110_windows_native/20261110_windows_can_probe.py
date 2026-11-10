"""Windows PCAN read-only identification; does not enable or move motors."""
import argparse
import struct
import time

ROLES = {
    '左臂': tuple(range(61, 68)),
    '右臂': tuple(range(51, 58)),
    '左手': (0x28,),
    '右手': (0x27,),
}


def probe_bus(bus, can_module, timeout=0.12):
    found = set()
    modes = {}
    for motor_id in (0x27, 0x28, *range(51, 58), *range(61, 68)):
        wrist = motor_id in (56, 57, 66, 67)
        request_id = motor_id + 0x600 if wrist else motor_id
        request = bytes((0x67, 0x0b, 0, 0, 0, 0, 0x04, 0x76)) if wrist else b'\x01'
        bus.send(can_module.Message(arbitration_id=request_id, data=request, is_extended_id=False))
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            message = bus.recv(remaining)
            if message is None:
                break
            if message.is_extended_id or message.is_remote_frame or message.is_error_frame or message.arbitration_id != request_id:
                continue
            data = bytes(message.data)
            if wrist and len(data) == 8 and data[:2] == bytes((motor_id, 0x0b)):
                found.add(motor_id)
                modes[motor_id] = struct.unpack('<i', data[2:6])[0]
            elif not wrist and data and data[0] == 1 and ((motor_id in (0x27, 0x28) and len(data) == 7) or (motor_id not in (0x27, 0x28) and len(data) >= 2)):
                found.add(motor_id)
    return found, modes


def main():
    parser = argparse.ArgumentParser(description='只读查询 PCAN 接口，不使能、不发送运动目标')
    parser.add_argument('--channels', nargs='+', default=[f'PCAN_USBBUS{i}' for i in range(1, 5)])
    args = parser.parse_args()
    import can
    any_open = False
    for channel in args.channels:
        try:
            bus = can.Bus(interface='pcan', channel=channel, bitrate=1000000, receive_own_messages=False)
            any_open = True
            try:
                found, modes = probe_bus(bus, can)
            finally:
                bus.shutdown()
            matches = [f'{name}: {len(set(ids) & found)}/{len(ids)}' for name, ids in ROLES.items() if set(ids) & found]
            print(f'{channel}: ' + ('；'.join(matches) if matches else '没有收到已识别响应'), flush=True)
            if modes:
                print('  腕部模式：' + ', '.join(f'{key}={value}' for key, value in sorted(modes.items())), flush=True)
        except Exception as error:
            print(f'{channel}: 打开或查询失败：{error}', flush=True)
    print('完整 ID 回复不等于物理左右已确认；请现场核对。', flush=True)
    if not any_open:
        raise SystemExit('没有打开任何 PCAN 通道，请检查 Windows PCAN 驱动、PCANBasic.dll 和设备连接。')


if __name__ == '__main__':
    main()
