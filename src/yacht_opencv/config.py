"""全局配置常量。"""

import sys
from pathlib import Path


# ── 路径 ──────────────────────────────────────────────
def _base_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent


BASE_DIR = _base_path()
TEMPLATES_DIR = BASE_DIR / "templates"
LOGO_PATH = str(BASE_DIR / "logo.ico")

# ── 模板匹配 ──────────────────────────────────────────
TEMPLATE_MATCH_THRESHOLD = 0.8
CAPTURE_INTERVAL = 0.2

# ── 锚点裁剪 ──────────────────────────────────────────
# 首次发现按钮后用 240x60 区域截图，匹配耗时从 320ms→~5ms
ANCHOR_CROP_W = 480
ANCHOR_CROP_H = 60
# ── 首次搜索 ──────────────────────────────────────────
# True=右下1/4区域搜索，False=全屏搜索（发现锚点后自动切换到240x60）
CAPTURE_BOTTOM_RIGHT = True
# ── 状态 → 播报文本映射 ──────────────────────────────
TEMPLATE_TEXT_MAP: dict[str, str] = {
    "三": "3",
    "二": "2",
    "一": "1",
    "投色子": "投色子",
    "再投一次": "再投一次",
    "最后一投": "最后一投",
}
