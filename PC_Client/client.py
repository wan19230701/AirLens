import socket
import struct
import cv2
import numpy as np
import time
import subprocess
import threading
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import os
import pyaudio
import wave
import sys

# 端口配置
VIDEO_PORT = 6677
AUDIO_PORT = 6678
PC_AUDIO_PORT = 6679


# 1. 手机音频接收器 (Phone -> PC)
class AudioStreamReceiver(threading.Thread):
    def __init__(self):
        super().__init__()
        self.sock = None
        self.running = False
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 44100
        self.CHUNK = 1024
        self.is_recording = False
        self.wave_file = None
        self.lock = threading.Lock()

    def connect(self, host, port):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((host, port))
            self.sock.settimeout(None)
            print(f"Phone Audio Connected")
            self.stream = self.p.open(format=self.FORMAT, channels=self.CHANNELS, rate=self.RATE, output=True,
                                      frames_per_buffer=self.CHUNK)
            self.running = True
            self.start()
            return True
        except Exception as e:
            print(f"Phone Audio Connection failed: {e}")
            return False

    def run(self):
        while self.running and self.sock:
            try:
                data = self.sock.recv(self.CHUNK)
                if not data: break
                self.stream.write(data)
                with self.lock:
                    if self.is_recording and self.wave_file:
                        self.wave_file.writeframes(data)
            except Exception as e:
                break

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()
        if self.sock: self.sock.close()

    def start_recording(self, filename):
        with self.lock:
            self.wave_file = wave.open(filename, 'wb')
            self.wave_file.setnchannels(self.CHANNELS)
            self.wave_file.setsampwidth(self.p.get_sample_size(self.FORMAT))
            self.wave_file.setframerate(self.RATE)
            self.is_recording = True

    def stop_recording(self):
        with self.lock:
            self.is_recording = False
            if self.wave_file:
                self.wave_file.close()
                self.wave_file = None

    def stop(self):
        self.running = False
        if self.sock: self.sock.close()


# 2. 电脑音频发送器 (PC -> Phone)
class PCAudioSender(threading.Thread):
    def __init__(self):
        super().__init__()
        self.sock = None
        self.running = False
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 44100
        self.CHUNK = 1024
        self.target_ip = None

    def connect_and_start(self, host):
        self.target_ip = host
        self.running = True
        self.start()

    def run(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.target_ip, PC_AUDIO_PORT))
            print("PC Audio Sending Connected!")

            self.stream = self.p.open(format=self.FORMAT,
                                      channels=self.CHANNELS,
                                      rate=self.RATE,
                                      input=True,
                                      frames_per_buffer=self.CHUNK)

            while self.running and self.sock:
                data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                self.sock.sendall(data)

        except Exception as e:
            print(f"PC Audio Send Error: {e}")
        finally:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if self.sock: self.sock.close()
            self.p.terminate()

    def stop(self):
        self.running = False


# 3. 视频接收器
class VideoStreamReceiver(threading.Thread):
    def __init__(self):
        super().__init__()
        self.sock = None
        self.running = False
        self.latest_frame = None
        self.lock = threading.Lock()

    def connect(self, host, port):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((host, port))
            self.sock.settimeout(None)
            print(f"Video Connected")
            self.running = True
            self.start()
            return True
        except Exception as e:
            print(f"Video Connection failed: {e}")
            return False

    def run(self):
        while self.running and self.sock:
            try:
                while True:
                    byte1 = self.sock.recv(1)
                    if not byte1:
                        self.running = False
                        return
                    if byte1 == b'\xBE':
                        byte2 = self.sock.recv(1)
                        if byte2 == b'\xEF': break

                length_data = self._recv_all(4)
                if not length_data: break
                length = struct.unpack(">L", length_data)[0]

                if length > 2000000: continue

                img_data = self._recv_all(length)
                if not img_data: break

                frame_data = np.frombuffer(img_data, dtype=np.uint8)
                frame = cv2.imdecode(frame_data, cv2.IMREAD_COLOR)

                if frame is not None:
                    with self.lock:
                        self.latest_frame = frame

            except Exception as e:
                self.running = False
                break
        if self.sock: self.sock.close()

    def _recv_all(self, count):
        buf = b''
        while count:
            try:
                newbuf = self.sock.recv(count)
                if not newbuf: return None
                buf += newbuf
                count -= len(newbuf)
            except:
                return None
        return buf

    def get_latest_frame(self):
        with self.lock:
            return self.latest_frame

    def send_command(self, cmd):
        if self.sock:
            try:
                msg = cmd.encode('utf-8')
                self.sock.sendall(struct.pack('>H', len(msg)) + msg)
            except Exception as e:
                print(f"Send Error: {e}")

    def stop(self):
        self.running = False
        if self.sock: self.sock.close()


# GUI 应用程序
class CameraApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AirLens")
        self.root.geometry("1100x800")

        self.video_receiver = VideoStreamReceiver()
        self.audio_receiver = AudioStreamReceiver()
        self.pc_audio_sender = None

        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))

        self.photo_dir = os.path.join(self.base_dir, "photo_save")
        self.video_dir = os.path.join(self.base_dir, "video_save")
        self.temp_dir = os.path.join(self.base_dir, "temp")
        for d in [self.photo_dir, self.video_dir, self.temp_dir]:
            if not os.path.exists(d): os.makedirs(d)

        self.is_recording = False
        self.video_writer = None
        self.start_time = 0

        self.rotate_index = 1

        self.is_talking = False

        self.create_ui()
        self.update_video_loop()

        # 绑定鼠标滚轮事件
        self.root.bind("<MouseWheel>", self.on_mouse_wheel)
        self.root.bind("<Button-4>", self.on_mouse_wheel)
        self.root.bind("<Button-5>", self.on_mouse_wheel)

    def create_ui(self):
        top_frame = tk.Frame(self.root, bg="#ddd", pady=5)
        top_frame.pack(side=tk.TOP, fill=tk.X)

        tk.Label(top_frame, text="手机 IP 地址:", bg="#ddd", font=("Arial", 12)).pack(side=tk.LEFT, padx=10)
        self.ip_entry = tk.Entry(top_frame, font=("Arial", 12), width=15)
        self.ip_entry.pack(side=tk.LEFT, padx=5)
        self.ip_entry.insert(0, "192.168.1.")

        self.btn_connect = tk.Button(top_frame, text="连接手机", command=self.connect_to_phone, bg="#4CAF50",
                                     fg="white", font=("Arial", 10, "bold"))
        self.btn_connect.pack(side=tk.LEFT, padx=10)

        self.video_frame = tk.Frame(self.root, bg="black")
        self.video_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        self.video_label = tk.Label(self.video_frame, bg="black")
        self.video_label.pack(expand=True, fill=tk.BOTH)

        self.control_panel = tk.Frame(self.root, width=220, bg="#f0f0f0")
        self.control_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.create_control_buttons()

    def create_control_buttons(self):
        padding_opts = {'padx': 15, 'pady': 12, 'fill': tk.X}

        tk.Label(self.control_panel, text="控制台", font=("Microsoft YaHei", 14, "bold"), bg="#f0f0f0").pack(pady=20)

        self.btn_photo = ttk.Button(self.control_panel, text="📷 拍照", command=self.take_photo, state="disabled")
        self.btn_photo.pack(**padding_opts)

        self.btn_record = ttk.Button(self.control_panel, text="🎥 开始录像", command=self.toggle_recording,
                                     state="disabled")
        self.btn_record.pack(**padding_opts)

        tk.Frame(self.control_panel, height=2, bg="#ccc").pack(fill=tk.X, pady=10)

        self.btn_talk = ttk.Button(self.control_panel, text="🎙 电脑喊话 (关)", command=self.toggle_talk,
                                   state="disabled")
        self.btn_talk.pack(**padding_opts)

        tk.Frame(self.control_panel, height=2, bg="#ccc").pack(fill=tk.X, pady=10)

        self.btn_switch = ttk.Button(self.control_panel, text="🔄 切换摄像头", command=self.switch_camera,
                                     state="disabled")
        self.btn_switch.pack(**padding_opts)

        self.btn_flash = ttk.Button(self.control_panel, text="🔦 手电筒", command=self.toggle_flash, state="disabled")
        self.btn_flash.pack(**padding_opts)

        tk.Frame(self.control_panel, height=2, bg="#ccc").pack(fill=tk.X, pady=10)
        tk.Label(self.control_panel, text="变焦 (Zoom)", bg="#f0f0f0", font=("Arial", 10)).pack()

        self.zoom_scale = tk.Scale(self.control_panel, from_=0, to=100, orient=tk.HORIZONTAL, bg="#f0f0f0",
                                   command=self.on_zoom_change)
        self.zoom_scale.set(0)
        self.zoom_scale.pack(padx=15, pady=5, fill=tk.X)

        tk.Frame(self.control_panel, height=2, bg="#ccc").pack(fill=tk.X, pady=10)

        self.btn_rotate = ttk.Button(self.control_panel, text="画面旋转 90°", command=self.manual_rotate)
        self.btn_rotate.pack(**padding_opts)

        self.status_label = tk.Label(self.control_panel, text="请先输入 IP 并连接", fg="red", bg="#f0f0f0")
        self.status_label.pack(side=tk.BOTTOM, pady=20)

        self.btn_quit = ttk.Button(self.control_panel, text="❌ 退出", command=self.close_app)
        self.btn_quit.pack(side=tk.BOTTOM, **padding_opts)

    def connect_to_phone(self):
        ip = self.ip_entry.get().strip()
        if not ip: return

        self.status_label.config(text="正在连接...", fg="orange")
        self.root.update()

        v_ok = self.video_receiver.connect(ip, VIDEO_PORT)
        a_ok = self.audio_receiver.connect(ip, AUDIO_PORT)

        if v_ok and a_ok:
            self.status_label.config(text="连接成功 (Wi-Fi)", fg="green")
            self.enable_buttons()
            self.btn_connect.config(state="disabled", text="已连接")
            self.ip_entry.config(state="disabled")
        else:
            self.status_label.config(text="连接失败", fg="red")
            self.video_receiver.stop()
            self.audio_receiver.stop()
            self.video_receiver = VideoStreamReceiver()
            self.audio_receiver = AudioStreamReceiver()

    def enable_buttons(self):
        for btn in [self.btn_photo, self.btn_record, self.btn_switch, self.btn_flash, self.btn_talk]:
            btn.config(state="normal")

    def on_zoom_change(self, value):
        float_val = float(value) / 100.0
        cmd = f"ZOOM:{float_val}"
        self.video_receiver.send_command(cmd)

    def on_mouse_wheel(self, event):
        current_val = self.zoom_scale.get()
        if event.num == 5 or event.delta < 0:
            new_val = current_val - 5
        elif event.num == 4 or event.delta > 0:
            new_val = current_val + 5
        else:
            return
        new_val = max(0, min(100, new_val))
        self.zoom_scale.set(new_val)

    def toggle_talk(self):
        if not self.is_talking:
            ip = self.ip_entry.get().strip()
            self.pc_audio_sender = PCAudioSender()
            self.pc_audio_sender.connect_and_start(ip)
            self.is_talking = True
            self.btn_talk.config(text="🎙 正在喊话 (开)")
            self.status_label.config(text="语音对讲开启", fg="blue")
        else:
            if self.pc_audio_sender:
                self.pc_audio_sender.stop()
                self.pc_audio_sender = None
            self.is_talking = False
            self.btn_talk.config(text="🎙 电脑喊话 (关)")
            self.status_label.config(text="语音对讲关闭", fg="green")

    # 3: 核心旋转逻辑
    def process_frame(self, frame):
        if frame is None: return None

        if self.rotate_index == 1:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif self.rotate_index == 2:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif self.rotate_index == 3:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        return frame

    def update_video_loop(self):
        if self.video_receiver.running:
            raw_frame = self.video_receiver.get_latest_frame()
            if raw_frame is not None:
                frame = self.process_frame(raw_frame)

                if self.is_recording and self.video_writer:
                    self.video_writer.write(frame)
                    cv2.circle(frame, (30, 30), 10, (0, 0, 255), -1)
                    duration = int(time.time() - self.start_time)
                    time_str = time.strftime("%H:%M:%S", time.gmtime(duration))
                    cv2.putText(frame, f"REC {time_str}", (50, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
                img = Image.fromarray(cv2image)
                win_width = self.video_frame.winfo_width()
                win_height = self.video_frame.winfo_height()
                if win_width > 1 and win_height > 1:
                    img.thumbnail((win_width, win_height))
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.imgtk = imgtk
                self.video_label.configure(image=imgtk)

        self.root.after(15, self.update_video_loop)

    def take_photo(self):
        raw_frame = self.video_receiver.get_latest_frame()
        if raw_frame is not None:
            frame = self.process_frame(raw_frame)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"IMG_{timestamp}.jpg"
            filepath = os.path.join(self.photo_dir, filename)
            cv2.imwrite(filepath, frame)
            self.status_label.config(text=f"已保存: {filename}", fg="blue")

    def toggle_recording(self):
        if not self.is_recording:
            raw_frame = self.video_receiver.get_latest_frame()
            if raw_frame is None: return
            frame = self.process_frame(raw_frame)
            h, w, _ = frame.shape
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            self.final_filename = f"VID_{timestamp}.mp4"
            self.temp_video_path = os.path.join(self.temp_dir, "temp_video.mp4")
            self.temp_audio_path = os.path.join(self.temp_dir, "temp_audio.wav")
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.video_writer = cv2.VideoWriter(self.temp_video_path, fourcc, 20.0, (w, h))
            self.audio_receiver.start_recording(self.temp_audio_path)
            self.is_recording = True
            self.start_time = time.time()
            self.btn_record.config(text="⏹ 停止录像")
            self.status_label.config(text="录制中...", fg="red")
        else:
            self.is_recording = False
            self.status_label.config(text="正在合并文件...", fg="orange")
            self.root.update()
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
            self.audio_receiver.stop_recording()
            output_path = os.path.join(self.video_dir, self.final_filename)
            self.merge_av(self.temp_video_path, self.temp_audio_path, output_path)
            self.btn_record.config(text="🎥 开始录像")
            self.status_label.config(text=f"录像完成: {self.final_filename}", fg="green")

    def merge_av(self, video_path, audio_path, output_path):
        try:
            cmd = ["ffmpeg", "-y", "-i", video_path, "-i", audio_path, "-c:v", "copy", "-c:a", "aac", "-shortest",
                   output_path]
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(cmd, check=True, startupinfo=startupinfo)
            try:
                os.remove(video_path)
                os.remove(audio_path)
            except:
                pass
        except Exception:
            self.status_label.config(text="合并失败 (检查FFmpeg)", fg="red")

    def switch_camera(self):
        self.video_receiver.send_command("SWITCH_CAMERA")
        if self.rotate_index == 1:
            self.rotate_index = 3
        else:
            self.rotate_index = 1

        self.status_label.config(text="切换摄像头", fg="orange")
        self.zoom_scale.set(0)

    def toggle_flash(self):
        self.video_receiver.send_command("TOGGLE_FLASH")

    # 4: 手动旋转触发
    def manual_rotate(self):
        self.rotate_index = (self.rotate_index + 1) % 4

        # 更新状态提示
        angles = ["0° (原始)", "90° (顺时针)", "180° (倒置)", "270° (逆时针)"]
        self.status_label.config(text=f"旋转模式: {angles[self.rotate_index]}", fg="blue")

    def close_app(self):
        if self.video_writer: self.video_writer.release()
        if self.pc_audio_sender: self.pc_audio_sender.stop()
        self.video_receiver.stop()
        self.audio_receiver.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = CameraApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close_app)
    root.mainloop()