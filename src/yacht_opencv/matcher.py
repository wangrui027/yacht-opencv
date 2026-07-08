"""OpenCV 模板匹配 —— 加载模板 → 全屏检索 → 返回匹配结果。"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from yacht_opencv.config import TEMPLATES_DIR, TEMPLATE_MATCH_THRESHOLD


class Template:
    """单个模板图片，包含其在屏幕上出现的位置信息。"""

    def __init__(self, name: str, path: Path) -> None:
        self.name = name  # 不含扩展名的文件名，例如 "投色子"
        self.path = path
        # 用 imdecode 代替 imread 以支持中文路径
        data = np.frombuffer(path.read_bytes(), dtype=np.uint8)
        self.image: np.ndarray = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if self.image is None:
            raise FileNotFoundError(f"无法加载模板：{path}")
        self.h, self.w = self.image.shape[:2]

    def __repr__(self) -> str:
        return f"<Template '{self.name}' {self.w}x{self.h}>"


def load_templates() -> list[Template]:
    """从 TEMPLATES_DIR 加载所有 .png 模板。

    返回列表按文件名排序保证顺序稳定。
    """
    if not TEMPLATES_DIR.is_dir():
        raise FileNotFoundError(f"模板目录不存在：{TEMPLATES_DIR}")

    templates: list[Template] = []
    for p in sorted(TEMPLATES_DIR.iterdir()):
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"):
            tpl = Template(p.stem, p)
            templates.append(tpl)
    return templates


def match_templates(
    screen: np.ndarray,
    templates: list[Template],
    threshold: float = TEMPLATE_MATCH_THRESHOLD,
) -> list[dict]:
    """在截图中查找所有匹配的模板。

    参数
    ----------
    screen : BGR 图像 (H, W, 3)
    templates : 模板列表
    threshold : 匹配阈值 (0-1)

    返回
    -------
    [{"name": str, "confidence": float, "rect": (x, y, w, h)}, ...]
    """
    results: list[dict] = []
    for tpl in templates:
        # 截图可能比模板小——跳过
        if screen.shape[0] < tpl.h or screen.shape[1] < tpl.w:
            continue

        result = cv2.matchTemplate(screen, tpl.image, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            x, y = max_loc
            results.append({
                "name": tpl.name,
                "confidence": float(round(max_val, 4)),
                "rect": (x, y, tpl.w, tpl.h),
            })

    # 按置信度降序
    results.sort(key=lambda r: r["confidence"], reverse=True)
    return results
