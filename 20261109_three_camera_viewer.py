"""Show three Orbbec RGB streams identified by serial number."""

import argparse
import importlib.util
from pathlib import Path
import threading
import time


def load_formats():
    path = Path(__file__).with_name("20261109_camera_formats.py")
    spec = importlib.util.spec_from_file_location("camera_formats", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rgb_devices():
    formats = load_formats()
    result = {}
    for path in Path("/sys/class/video4linux").glob("video*"):
        node = "/dev/" + path.name
        try:
            supported = formats.list_formats(node)
        except OSError:
            continue
        if not any(item.startswith("YUYV:") for item in supported):
            continue
        device = path / "device"
        if formats.usb_property(device, "idVendor").lower() != "2bc5":
            continue
        serial = formats.usb_property(device, "serial")
        if serial == "?" or serial in result:
            raise RuntimeError("相机序列号缺失或重复，无法安全区分：" + serial)
        result[serial] = node
    return dict(sorted(result.items()))


def open_camera(node):
    import cv2
    camera = cv2.VideoCapture(node, cv2.CAP_V4L2)
    if not camera.isOpened():
        camera.release()
        raise RuntimeError("无法打开 " + node)
    camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_FPS, 15)
    return camera


def check_cameras(devices):
    cameras = []
    try:
        for serial, node in devices.items():
            cameras.append((serial, node, open_camera(node)))
        for serial, node, camera in cameras:
            for _ in range(15):
                ok, frame = camera.read()
                if not ok:
                    break
            if not ok or frame is None or not frame.size:
                raise RuntimeError(f"{serial} {node} 无法读取画面")
            print(f"{serial} {node}: {frame.shape[1]}x{frame.shape[0]}, 平均亮度 {frame.mean():.1f}, 像素标准差 {frame.std():.1f}")
        return 0
    finally:
        for _, _, camera in cameras:
            camera.release()


def show_cameras(devices):
    import cv2
    import tkinter as tk
    from PIL import Image, ImageTk

    root = tk.Tk()
    root.title("三路 Orbbec 相机预览")
    stop = threading.Event()
    for column, (serial, node) in enumerate(devices.items()):
        frame = tk.Frame(root)
        frame.grid(row=0, column=column, padx=6, pady=6, sticky="n")
        tk.Label(frame, text=serial, font=("wenquanyi bitmap song", 14)).pack()
        label = tk.Label(frame, text="正在连接…", width=40, height=20)
        label.pack()

        def worker(serial=serial, node=node, label=label):
            camera = None
            try:
                camera = open_camera(node)
                while not stop.is_set():
                    ok, image = camera.read()
                    if not ok or image is None:
                        raise RuntimeError("画面读取失败")
                    image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
                    image.thumbnail((480, 360))

                    def display(image=image, label=label):
                        if not stop.is_set():
                            photo = ImageTk.PhotoImage(image)
                            label.configure(image=photo, text="", width=0, height=0)
                            label.image = photo
                    root.after(0, display)
                    time.sleep(0.05)
            except Exception as error:
                if not stop.is_set():
                    root.after(0, lambda error=error: label.configure(text=f"{serial}: {error}"))
            finally:
                if camera is not None:
                    camera.release()

        threading.Thread(target=worker, daemon=True).start()

    def close():
        stop.set()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="按序列号显示三台 Orbbec 的 RGB 视频")
    parser.add_argument("--check", action="store_true", help="同时打开相机并读取一帧后退出")
    args = parser.parse_args()
    devices = rgb_devices()
    if len(devices) != 3:
        raise SystemExit(f"需要三台 Orbbec RGB 相机，当前找到 {len(devices)} 台：{devices}")
    for serial, node in devices.items():
        print(f"{serial}: {node}", flush=True)
    return check_cameras(devices) if args.check else show_cameras(devices)


if __name__ == "__main__":
    main()
