"""Windows camera indices are selected by the operator, not device identity."""
import json
from pathlib import Path

def rgb_devices():
    config = Path(__file__).with_name('20261110_camera_indices.json')
    if not config.exists():
        return {}
    values = json.loads(config.read_text(encoding='utf-8'))
    if not isinstance(values, list) or len(values) > 3 or any(type(x) is not int or x < 0 or x > 20 for x in values) or len(set(values)) != len(values):
        raise ValueError('相机配置须为最多三个不重复的 0～20 整数')
    return {f'相机索引 {index}': index for index in values}

def open_camera(node):
    import cv2
    camera = cv2.VideoCapture(node, cv2.CAP_DSHOW)
    if not camera.isOpened():
        camera.release()
        raise RuntimeError(f'无法打开相机索引 {node}')
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_FPS, 15)
    return camera
