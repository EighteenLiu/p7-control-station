"""P7 dual-arm, O6 dual-hand and Orbbec RGB control station."""

import argparse
import importlib.util
import math
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import font as tkfont, messagebox, ttk


def load_sibling(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = load_sibling('p7_probe', '20261110_windows_can_probe.py')
camera_support = load_sibling('camera_viewer', '20261110_windows_camera.py')
ARM_NAMES = ('肩部俯仰', '肩部横滚', '肩部偏转', '肘部俯仰', '肘部偏转', '腕部俯仰', '腕部横滚')
HAND_NAMES = ('拇指弯曲', '拇指侧摆', '食指', '中指', '无名指', '小指')
STEP_RAD = math.radians(1.0)


def identify_devices():
    mapping = {}
    roles = {'左臂': 'left_arm', '右臂': 'right_arm', '左手': 'left_hand', '右手': 'right_hand'}
    import can
    for channel in (f'PCAN_USBBUS{i}' for i in range(1, 5)):
        with can.Bus(interface='pcan', channel=channel, bitrate=1000000, receive_own_messages=False) as bus:
            answers, _ = probe.probe_bus(bus, can)
        for label, expected in probe.ROLES.items():
            if all(item in answers for item in expected):
                key = roles[label]
                if key in mapping:
                    raise RuntimeError(f'{label}在多个 CAN 接口回复，无法安全选择')
                mapping[key] = channel
    return mapping


def make_conservative_p7():
    """Apply lower telemetry load from the start of P7 construction."""
    from linkerbot import P7
    from linkerbot.arm.a7.motor import SensorType

    class ConservativeP7(P7):
        def start_polling(self, intervals=None):
            if intervals is None:
                intervals = {
                    SensorType.POSITION: 0.1,
                    SensorType.VELOCITY: 0.1,
                    SensorType.TORQUE: 0.5,
                    SensorType.TEMPERATURE: 1.0,
                }
            return super().start_polling(intervals)

    return ConservativeP7


class ArmWorker:
    """Serializes short official SDK moves; stop takes effect between segments."""
    def __init__(self, arm, report):
        self.arm, self.report = arm, report
        self.lock = threading.Lock()
        self.target = None
        self.running = True
        self.enabled = False
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def set_target(self, values):
        with self.lock:
            self.target = list(values)

    def pause(self):
        with self.lock:
            self.target = None

    def run(self):
        while self.running:
            with self.lock:
                target = self.target[:] if self.target is not None and self.enabled else None
            if target is None:
                time.sleep(0.05)
                continue
            try:
                if getattr(self.arm, '_bus_error', None):
                    raise RuntimeError('CAN 通信故障')
                states = [motor.angle for motor in self.arm._motors]
                if len(states) != 7 or any(time.time() - item.timestamp > 1.0 for item in states):
                    raise RuntimeError('机械臂位置反馈超时')
                current = self.arm.get_angles()
                delta = [max(-STEP_RAD, min(STEP_RAD, t - c)) for t, c in zip(target, current)]
                if max(abs(d) for d in delta) < math.radians(0.15):
                    time.sleep(0.08)
                    continue
                self.arm.move_j([c + d for c, d in zip(current, delta)], blocking=True)
            except Exception as error:
                self.pause()
                self.report('机械臂发送失败，已停止后续目标：' + str(error))
                time.sleep(0.1)

    def close(self):
        self.pause()
        self.running = False
        self.thread.join(3)
        if self.thread.is_alive():
            raise RuntimeError('机械臂运动线程仍未结束，保留连接')
        self.arm.close()


class App:
    def __init__(self, root, offline=False):
        self.root, self.offline = root, offline
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.mapping = {}
        self.arms, self.hands, self.arm_vars, self.hand_vars, self.arm_scales = {}, {}, {}, {}, {}
        self.home_buttons = {}
        self.enabled = {'left': False, 'right': False}
        self.pending = {}
        self.syncing = set()
        self.connecting = set()
        self.camera_frames = {}
        self.camera_lock = threading.Lock()
        self.hand_locks = {'left': threading.Lock(), 'right': threading.Lock()}
        self.hand_generation = {'left': 0, 'right': 0}
        root.title('P7 双臂 O6 双手控制站 - Windows 测试版')
        root.geometry('1500x920')
        for name in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont'):
            tkfont.nametofont(name).configure(family='wenquanyi bitmap song', size=16)
        root.option_add('*Font', '{wenquanyi bitmap song} 16')
        style = ttk.Style(root)
        for name in ('TLabel', 'TButton', 'TNotebook.Tab'):
            style.configure(name, font=('wenquanyi bitmap song', 16))
        self.status = tk.StringVar(value='Windows 测试版：机械臂运动尚未验证')
        top = ttk.Frame(root)
        top.pack(fill='x', padx=8, pady=5)
        ttk.Button(top, text='识别设备', command=self.discover).pack(side='left')
        ttk.Button(top, text='停止后续目标', command=self.pause_all).pack(side='left', padx=5)
        ttk.Label(top, textvariable=self.status).pack(side='left', padx=8)
        main = ttk.Panedwindow(root, orient='horizontal')
        main.pack(fill='both', expand=True)
        tabs = ttk.Notebook(main)
        main.add(tabs, weight=1)
        for side, label in (('left', '左侧'), ('right', '右侧')):
            pane = ttk.Frame(tabs)
            tabs.add(pane, text=label)
            self.build_side(pane, side)
        view = ttk.Frame(main)
        main.add(view, weight=2)
        self.camera_labels = []
        for i in range(3):
            label = ttk.Label(view, text='等待相机', anchor='center')
            label.pack(fill='both', expand=True, padx=4, pady=3)
            self.camera_labels.append(label)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(80, self.drain)
        if not offline:
            threading.Thread(target=self.start_cameras, daemon=True).start()

    def build_side(self, parent, side):
        controls = ttk.Frame(parent)
        controls.pack(fill='x', pady=4)
        for title, action in (
            ('连接机械臂（未验证）', lambda: self.status.set('Windows 机械臂运动尚未验证，暂不可连接')),
            ('使能机械臂（未验证）', lambda: self.status.set('Windows 机械臂运动尚未验证，暂不可使能')),
            ('连接手', lambda: self.connect_hand(side)),
            ('停止该侧', lambda: self.pause_side(side)),
        ):
            ttk.Button(controls, text=title, command=action).pack(side='left', padx=2)
        self.home_buttons[side] = ttk.Button(parent, text='恢复至零位', command=lambda: self.return_home(side), state='disabled')
        self.home_buttons[side].pack(anchor='w', pady=3)
        ttk.Label(parent, text='机械臂角度（度）').pack(anchor='w')
        self.arm_vars[side] = []
        self.arm_scales[side] = []
        for i, name in enumerate(ARM_NAMES):
            var = tk.DoubleVar(value=0)
            self.arm_vars[side].append(var)
            scale = self.slider(parent, name, var, -180, 180, lambda _v, s=side: self.arm_change(s))
            scale.state(['disabled'])
            self.arm_scales[side].append(scale)
        ttk.Label(parent, text='O6 手部目标（0～100）').pack(anchor='w', pady=(10, 0))
        self.hand_vars[side] = []
        for i, name in enumerate(HAND_NAMES):
            var = tk.DoubleVar(value=0)
            self.hand_vars[side].append(var)
            self.slider(parent, name, var, 0, 100, lambda _v, s=side: self.hand_change(s))

    def slider(self, parent, name, var, lower, upper, command):
        row = ttk.Frame(parent)
        row.pack(fill='x')
        ttk.Label(row, text=name, width=10).pack(side='left')
        scale = ttk.Scale(row, from_=lower, to=upper, variable=var, command=command)
        scale.pack(side='left', fill='x', expand=True)
        display = tk.StringVar(value=f'{var.get():.1f}')
        var.trace_add('write', lambda *_: display.set(f'{var.get():.1f}'))
        ttk.Label(row, textvariable=display, width=7).pack(side='right')
        return scale

    def post(self, message):
        self.events.put(('status', message))

    def background(self, function):
        def run():
            try:
                function()
            except Exception as error:
                self.post('操作失败：' + str(error))
        threading.Thread(target=run, daemon=True).start()

    def discover(self):
        if self.offline:
            self.status.set('离线模式不访问设备')
            return
        if self.arms or self.hands:
            self.status.set('请先关闭程序再重新识别，避免占用中的设备被重复查询')
            return
        def work():
            mapping = identify_devices()
            self.events.put(('mapping', mapping))
        self.status.set('正在只读识别 CAN 设备…')
        self.background(work)

    def connect_arm(self, side):
        if self.offline:
            return
        key = side + '_arm'
        if key not in self.mapping or side in self.arms:
            self.status.set('请先成功识别该机械臂；已连接则无需重复连接')
            return
        if key in self.connecting:
            return
        if not messagebox.askokcancel('连接机械臂', '厂商 SDK 初始化会让腕部电机进入休止状态，可能松动下落，并可能写入腕部控制模式。请先支撑机械臂，确认工作区域安全后继续。'):
            return
        self.connecting.add(key)
        def work():
            try:
                p7_class = make_conservative_p7()
                arm = p7_class(side=side, interface_name=self.mapping[key], interface_type='pcan')
                try:
                    angles = arm.get_angles()
                    limits = arm.get_joint_limits()
                except Exception:
                    arm.close()
                    raise
                self.events.put(('arm_connected', side, arm, angles, limits))
            finally:
                self.events.put(('connection_done', key))
        self.background(work)

    def connect_hand(self, side):
        if self.offline:
            return
        key = side + '_hand'
        if key not in self.mapping or side in self.hands:
            self.status.set('请先成功识别该手；已连接则无需重复连接')
            return
        if key in self.connecting:
            return
        self.connecting.add(key)
        def work():
            try:
                from linkerbot import O6
                hand = O6(side=side, interface_name=self.mapping[key], interface_type='pcan', angle_mapping_path=Path(__file__).with_name('20261109_o6_angle_mapping.toml'))
                try:
                    values = hand.angle.get_blocking(timeout_ms=1000).angles.to_list()
                except Exception:
                    hand.close()
                    raise
                self.events.put(('hand_connected', side, hand, values))
            finally:
                self.events.put(('connection_done', key))
        self.background(work)

    def enable_arm(self, side):
        worker = self.arms.get(side)
        if not worker or self.enabled[side]:
            self.status.set('请先连接该机械臂；已使能则无需重复操作')
            return
        key = side + '_enable'
        if key in self.connecting:
            return
        if not messagebox.askokcancel('使能机械臂', '使能可能使关节短暂失力或发生运动。滑块和零位使用曾出现晃动及指令积压的旧控制逻辑，停止后旧指令仍可能发送。请支撑机械臂并确认实体急停可用。继续？'):
            return
        self.connecting.add(key)
        def work():
            try:
                worker.arm.enable()
                values = worker.arm.get_angles()
                self.events.put(('arm_enabled', side, values))
            finally:
                self.events.put(('connection_done', key))
        self.background(work)

    def return_home(self, side):
        if not self.enabled.get(side) or side not in self.arms:
            self.status.set('机械臂未连接或未使能，无法恢复零位')
            return
        limits = self.arms[side].arm.get_joint_limits()
        if len(limits) != 7 or any(not lo <= 0.0 <= hi for lo, hi in limits):
            self.status.set('零位不在当前机械臂限位内，未发送')
            return
        if not messagebox.askokcancel('恢复至零位', '该侧机械臂将移动至厂商零位（自然下垂）。请确认路径无障碍，且急停可用。继续？'):
            return
        self.syncing.add(side)
        try:
            for variable in self.arm_vars[side]:
                variable.set(0.0)
        finally:
            self.syncing.discard(side)
        self.arms[side].set_target([0.0] * 7)
        self.status.set('已设置该侧机械臂零位目标')

    def arm_change(self, side):
        if side in self.syncing or not self.enabled[side]:
            return
        values = [math.radians(v.get()) for v in self.arm_vars[side]]
        limits = self.arms[side].arm.get_joint_limits()
        if any(not lo <= value <= hi for value, (lo, hi) in zip(values, limits)):
            self.status.set('目标超出当前机械臂限位，未发送')
            return
        self.arms[side].set_target(values)

    def hand_change(self, side):
        if side in self.syncing or side not in self.hands:
            return
        if side in self.pending:
            self.root.after_cancel(self.pending[side])
        self.pending[side] = self.root.after(80, lambda: self.send_hand(side))

    def send_hand(self, side):
        self.pending.pop(side, None)
        values = [max(0.0, min(100.0, v.get())) for v in self.hand_vars[side]]
        generation = self.hand_generation[side]
        def work():
            with self.hand_locks[side]:
                if generation == self.hand_generation[side] and not self.stop.is_set():
                    hand = self.hands[side]
                    state = hand.angle.get_snapshot()
                    if state is None or time.time() - state.timestamp > 1.0:
                        raise RuntimeError(f'{side} 手部反馈超时，未发送目标')
                    hand.angle.set_angles(values)
        self.background(work)

    def pause_side(self, side):
        self.hand_generation[side] += 1
        if side in self.arms:
            self.arms[side].pause()
        if side in self.pending:
            self.root.after_cancel(self.pending.pop(side))
        self.status.set('已清除后续目标；当前短段运动完成后停止')

    def pause_all(self):
        for side in ('left', 'right'):
            self.pause_side(side)

    def start_cameras(self):
        try:
            devices = camera_support.rgb_devices()
        except Exception as error:
            self.post('相机识别失败：' + str(error))
            return
        for index, (serial, node) in enumerate(devices.items()):
            if index >= 3:
                break
            threading.Thread(target=self.camera_worker, args=(index, serial, node), daemon=True).start()
        self.post(f'已发现 {len(devices)} 台 RGB 相机')

    def camera_worker(self, index, serial, node):
        import cv2
        from PIL import Image
        camera = None
        try:
            camera = camera_support.open_camera(node)
            while not self.stop.is_set():
                ok, frame = camera.read()
                if not ok:
                    raise RuntimeError('读取失败')
                image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                image.thumbnail((550, 260))
                with self.camera_lock:
                    self.camera_frames[index] = (serial, image)
                time.sleep(0.1)
        except Exception as error:
            self.post(f'相机 {serial}: {error}')
        finally:
            if camera is not None:
                camera.release()

    def drain(self):
        from PIL import ImageTk
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == 'status':
                    self.status.set(event[1])
                elif kind == 'mapping':
                    self.mapping = event[1]
                    self.status.set('识别结果：' + str(self.mapping))
                elif kind == 'connection_done':
                    self.connecting.discard(event[1])
                elif kind == 'arm_connected':
                    _, side, arm, values, limits = event
                    self.arms[side] = ArmWorker(arm, self.post)
                    self.syncing.add(side)
                    for scale, (lower, upper) in zip(self.arm_scales[side], limits):
                        scale.configure(from_=math.degrees(lower), to=math.degrees(upper))
                    for var, value in zip(self.arm_vars[side], values):
                        var.set(round(math.degrees(value), 1))
                    self.syncing.discard(side)
                    self.status.set(f'{side} 机械臂已连接，未使能；已加载 {len(limits)} 个关节限位')
                elif kind == 'arm_enabled':
                    _, side, values = event
                    self.syncing.add(side)
                    for var, value in zip(self.arm_vars[side], values):
                        var.set(round(math.degrees(value), 1))
                    self.syncing.discard(side)
                    self.enabled[side] = True
                    self.arms[side].enabled = True
                    self.home_buttons[side].configure(state='disabled')
                    for scale in self.arm_scales[side]:
                        scale.state(['disabled'])
                    self.status.set(f'{side} 已发送使能请求；注意晃动和指令积压尚未修复')
                elif kind == 'hand_connected':
                    _, side, hand, values = event
                    self.syncing.add(side)
                    for var, value in zip(self.hand_vars[side], values):
                        var.set(round(value, 1))
                    self.syncing.discard(side)
                    self.hands[side] = hand
                    self.status.set(f'{side} 手已连接，滑块已读取当前位置')
        except queue.Empty:
            pass
        with self.camera_lock:
            frames, self.camera_frames = self.camera_frames, {}
        for index, (serial, image) in frames.items():
            photo = ImageTk.PhotoImage(image)
            self.camera_labels[index].configure(image=photo, text=serial, compound='top')
            self.camera_labels[index].image = photo
        if not self.stop.is_set():
            self.root.after(80, self.drain)

    def close(self):
        if self.connecting:
            self.status.set('设备正在连接，请等待连接结束再关闭')
            return
        if self.arms and not messagebox.askokcancel('关闭程序', '关闭后腕部电机的通信心跳会停止，关节可能松动。请先支撑机械臂，确认后关闭。'):
            return
        self.pause_all()
        for side, worker in list(self.arms.items()):
            try:
                worker.close()
            except Exception as error:
                self.status.set('关闭失败：' + str(error))
                return
            self.enabled[side] = False
            del self.arms[side]
        self.stop.set()
        for hand in self.hands.values():
            hand.close()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--offline', action='store_true', help='只显示界面，不连接硬件或相机')
    args = parser.parse_args()
    root = tk.Tk()
    App(root, offline=args.offline)
    root.mainloop()


if __name__ == '__main__':
    main()
