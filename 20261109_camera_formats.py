"""List Linux camera capture formats without starting a video stream."""

import fcntl
import os
from pathlib import Path
import struct


VIDIOC_ENUM_FMT = 0xC0405602
FORMAT = struct.Struct("=III32sII3I")


def usb_property(path, name):
    resolved = path.resolve()
    for parent in (resolved,) + tuple(resolved.parents):
        try:
            return (parent / name).read_text().strip()
        except OSError:
            pass
    return "?"


def list_formats(node):
    fd = os.open(node, os.O_RDONLY | os.O_NONBLOCK)
    result = []
    try:
        for index in range(128):
            data = bytearray(FORMAT.pack(index, 1, 0, b"", 0, 0, 0, 0, 0))
            try:
                fcntl.ioctl(fd, VIDIOC_ENUM_FMT, data, True)
            except OSError:
                break
            _, _, _, description, fourcc, _, _, _, _ = FORMAT.unpack(data)
            code = fourcc.to_bytes(4, "little").decode("ascii", errors="replace")
            result.append(code + ":" + description.split(b"\0", 1)[0].decode("utf-8", errors="replace"))
    finally:
        os.close(fd)
    return result


def main():
    for path in sorted(Path("/sys/class/video4linux").glob("video*"), key=lambda p: int(p.name[5:])):
        node = "/dev/" + path.name
        try:
            formats = list_formats(node)
        except OSError as error:
            print(f"{node}: 无法读取格式：{error}")
            continue
        if formats:
            device = path / "device"
            print(f"{node} | 序列号={usb_property(device, 'serial')} | 格式={', '.join(formats)}")


if __name__ == "__main__":
    main()
