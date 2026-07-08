"""屏幕截图工具 —— 使用 mss 高速捕获屏幕。"""

from __future__ import annotations

import numpy as np
import mss


def capture_screen(bbox: tuple[int, int, int, int] | None = None) -> np.ndarray:
    """截取屏幕，返回 BGR numpy 数组（兼容 OpenCV）。

    参数
    ----------
    bbox : (left, top, right, bottom) 截图区域像素坐标
          None = 截取全屏（含多显示器）
    """
    with mss.mss() as sct:
        if bbox:
            left, top, right, bottom = bbox
            monitor = {"left": left, "top": top, "width": right - left, "height": bottom - top}
            img = sct.grab(monitor)
        else:
            # monitor 0 = 所有显示器的虚拟桌面
            img = sct.grab(sct.monitors[0])

        # mss 返回 BGRA (H, W, 4), 去掉 A 通道得到 BGR
        arr = np.frombuffer(img.rgb, dtype=np.uint8).reshape(img.size.height, img.size.width, 3)
        # img.rgb 已经是 RGB 格式，需要翻转 → BGR for OpenCV
        return arr[:, :, ::-1].copy()
