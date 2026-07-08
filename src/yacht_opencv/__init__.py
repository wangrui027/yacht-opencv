"""游艇骰子 CV 助手 - 基于 OpenCV 的屏幕识别 + 语音通知。"""

__version__ = "0.1.0"


def main():
    """程序入口点：启动系统托盘应用。"""
    from yacht_opencv.tray import run_tray

    run_tray()
