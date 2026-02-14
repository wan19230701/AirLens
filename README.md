AirLens  
AirLens is a powerful, low-latency wireless webcam and intercom system that turns your Android phone into a network camera for your PC. Built with Android (Kotlin) and Python, it operates entirely over a local Wi-Fi network—no USB cables required.

Looking for the Android-to-Android version?
Check out my new standalone project: AirLens-Mobile

Key Features  
1. Wireless Streaming: Real-time, low-latency video streaming via Wi-Fi (TCP Socket).  
2. Two-Way Intercom:  
   ① Stream audio from phone microphone to PC.  
   ② "PC Talk": Send voice from PC microphone to phone speakers (Push-to-Talk).  
3. Remote Control Panel: Control the phone camera directly from the PC GUI:  
   ① Zoom Control: Smooth zoom using a slider or mouse scroll wheel.  
   ② Rotation: Correct image orientation (0°, 90°, 180°, 270°) with a single click.  
   ③ Switch Camera: Toggle between front and back cameras.  
   ④ Flashlight/torch: Toggle the phone's torch remotely.  
4. Recording & Snapshot:  
   ① Take snapshots saved directly to your PC.  
   ② Record video with synchronized audio (auto-merged via bundled FFmpeg).  
5. Background Mode: Supports Android Picture-in-Picture (PiP) mode. The camera continues streaming even when the app is minimized or the phone is on the home screen.

Quick Start (For Users)  
No coding knowledge required. Just download and run!  
1. Download: Go to the Releases page of this repository.  
2. Install Android App: Download AirLens.apk and install it on your Android phone.  
3. Run PC Client:  
   ① Download the AirLens_PC.zip (or the folder containing the .exe).  
   ② Important: Ensure ffmpeg.exe is in the same folder as AirLens.exe (it is included in the release package).  
   ③ Double-click AirLens.exe to launch.  
4. Connect:  
   ① Open the app on your phone. Note the IP Address displayed (e.g., 192.168.1.x).  
   ② Enter this IP into the PC client and click Connect.  

Development Setup (For Developers)  
If you want to modify the source code, follow these steps.  
1. Prerequisites  
  ① Android: Android Studio Ladybug or newer.  
  ② PC: Python 3.10+, ffmpeg installed and added to system PATH.  
2. Android Client (Android_App/)  
  ① Open the folder in Android Studio.  
  ② Sync Gradle and build the project.  
  ③ Deploy to your device via USB debugging.  
3. PC Client (PC_Client/)  
  ① Install dependencies:  
      Bash  
      pip install opencv-python numpy pyaudio Pillow pyinstaller  
  ② Run the script:  
      Bash  
      python client.py  

Project Structure  
  AirLens/  
  ├── Android_App/       # Android Studio Project (Kotlin)  
  │   ├── app/           # Source code, Manifest, Resources  
  │   └── ...  
  └── PC_Client/         # PC Control Client (Python)  
      ├── client.py      # Main application entry  
      ├── icon.ico       # App Icon  
      └── requirements.txt  

License  
This project is licensed under the MIT License.  


AirLens - 安卓局域网无线摄像头与对讲系统  
AirLens 是一个开源的局域网音视频传输系统，它可以将你的 Android 手机变身为电脑的高清无线摄像头，并支持双向语音对讲。基于 Android (Kotlin) 和 Python 开发，无需 USB 线，连接同一个 Wi-Fi 即可使用。

核心功能  
1. 无线画面传输: 基于 TCP Socket 的低延迟局域网视频流传输。  
2. 双向语音对讲:  
   ① 支持手机麦克风声音传输至电脑播放。  
   ② 电脑喊话功能: 点击电脑端“喊话”按钮，即可将声音实时传送到手机扬声器播放。  
3. 全能控制台: 在电脑端 GUI 界面完全控制手机相机：  
   ① 变焦 (Zoom): 支持滑动条或鼠标滚轮实时调整手机镜头焦距。  
   ② 画面旋转: 支持 90°/180°/270° 循环旋转，矫正画面方向。  
   ③ 切换镜头: 一键切换前置/后置摄像头。  
   ④ 闪光灯/手电筒: 远程开启/关闭手机补光灯。  
4. 录像与截图:  
   ① 支持一键拍照保存至电脑。  
   ② 支持音视频同步录制（自动调用内置 FFmpeg 合成 MP4 文件）。  
5. 后台运行 (画中画): 支持 Android 画中画 (PiP) 模式。按 Home 键返回桌面后，App 会变成悬浮小窗继续传输画面，不会中断。  

快速开始 (普通用户)  
无需配置开发环境，下载即用！  
1. 下载: 前往本仓库的 Releases (发行版) 页面。  
2. 安装手机端: 下载 AirLens.apk 并安装到你的 Android 手机上。  
3. 运行电脑端:  
   ① 下载电脑端压缩包（或 AirLens.exe）。  
   ② 注意: ffmpeg.exe 已经打包在发布文件中，请确保它和 AirLens.exe 在同一个文件夹内。  
   ③ 双击运行 AirLens.exe。  
4. 连接:  
   ① 确保手机和电脑连接到了同一个 Wi-Fi。  
   ② 打开手机 App，查看屏幕上显示的 本机 IP (例如 192.168.1.5)。  
   ③ 在电脑端输入该 IP，点击 连接手机。  

开发环境配置 (开发者)  
如果你想修改源码或贡献代码，请参考以下步骤。  
1. 前置要求  
  ① Android: Android Studio Ladybug 或更高版本。  
  ② PC: Python 3.10+，且需自行安装 ffmpeg 并配置到系统环境变量中（源码运行模式下）。  
2. Android 端 (Android_App/)  
  ① 使用 Android Studio 打开该目录。  
  ② 等待 Gradle Sync 完成。  
  ③ 连接真机并运行。  
3. 电脑端 (PC_Client/)  
  ① 安装依赖库:  
      Bash  
      pip install opencv-python numpy pyaudio Pillow pyinstaller  
  ② 运行脚本:  
      Bash  
      python client.py  

目录结构  
  AirLens/  
  ├── Android_App/       # 安卓工程源码 (Kotlin)  
  │   ├── app/           # 核心代码、Manifest配置文件  
  │   └── ...  
  └── PC_Client/         # 电脑端源码 (Python)  
      ├── client.py      # 主程序入口  
      ├── icon.ico       # 程序图标  
      └── requirements.txt # Python 依赖列表  

开源协议  
本项目遵循 MIT 开源协议。
