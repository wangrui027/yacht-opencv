"""系统托盘应用 —— 后台截屏识别循环 + 托盘菜单控制。"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from pathlib import Path

import cv2
import pystray
import win32api
import win32con
from PIL import Image

from yacht_opencv.config import (
    ANCHOR_CROP_H,
    ANCHOR_CROP_W,
    CAPTURE_BOTTOM_RIGHT,
    CAPTURE_INTERVAL,
    LOGO_PATH,
    TEMPLATE_MATCH_THRESHOLD,
    TEMPLATE_TEXT_MAP,
)
from yacht_opencv.matcher import Template, load_templates, match_templates
from yacht_opencv.notifier import speak
from yacht_opencv.overlay import create_overlay, destroy_overlay, show_overlay
from yacht_opencv.screen import capture_screen
from yacht_opencv.settings import VOICES, load as load_settings, save as save_settings

logger = logging.getLogger(__name__)

# ── 全局状态 ──────────────────────────────────────────
_running = False
_thread: threading.Thread | None = None
_templates: list[Template] = []
_last_text: str | None = None
_prev_md5: bytes | None = None
_anchor: tuple[int, int] | None = None

# ── 持久化状态（从 settings.json 加载）──────────────────
_tts_voice: str = "zh-CN-YunjianNeural"
_overlay_box_on = False
_save_screenshot_on = False
_save_dir: Path | None = None
_save_seq = 0


def _load_all_settings() -> None:
    """从 settings.json 读取，覆盖全局变量。"""
    global _tts_voice, _overlay_box_on, _save_screenshot_on
    s = load_settings()
    _tts_voice = s.get("tts_voice", "zh-CN-YunjianNeural")
    _overlay_box_on = s.get("overlay_box_on", False)
    _save_screenshot_on = s.get("save_screenshot_on", False)
    logger.info("已加载配置: 音色=%s 检测框=%s 保存截图=%s", _tts_voice, _overlay_box_on, _save_screenshot_on)


def _persist() -> None:
    """将当前状态写入 settings.json。"""
    data = {
        "tts_voice": _tts_voice,
        "overlay_box_on": _overlay_box_on,
        "save_screenshot_on": _save_screenshot_on,
    }
    for k, v in data.items():
        if not isinstance(v, (str, bool, int, float, type(None))):
            logger.error("配置值异常，忽略保存: %s = %s (%s)", k, v, type(v).__name__)
            return
    save_settings(data)


# ── 菜单回调 ──────────────────────────────────────────
def _reset_anchor(_menu_item: object = None) -> None:
    """重置锚点，回到 1/4 区域重新发现投色子。"""
    global _anchor
    _anchor = None
    logger.info("锚点已重置，重新搜索")


def _toggle_overlay(_menu_item: object = None) -> None:
    global _overlay_box_on
    _overlay_box_on = not _overlay_box_on
    if _overlay_box_on:
        create_overlay()
        logger.info("检测框已开启")
    else:
        show_overlay(None)
        destroy_overlay()
        logger.info("检测框已关闭")
    _persist()


def _toggle_save(_menu_item: object = None) -> None:
    global _save_screenshot_on, _save_dir, _save_seq
    _save_screenshot_on = not _save_screenshot_on
    if _save_screenshot_on:
        _save_dir = Path.cwd() / "screenshots" / time.strftime("%Y%m%d_%H%M%S")
        _save_dir.mkdir(parents=True, exist_ok=True)
        _save_seq = 0
        logger.info("截图保存至: %s", _save_dir)
    else:
        _save_dir = None
        logger.info("截图保存已关闭")
    _persist()


def _set_tts_voice(voice_id: str) -> None:
    global _tts_voice
    if voice_id == _tts_voice:
        return  # 同音色忽略
    _tts_voice = voice_id
    logger.info("音色切换至: %s", voice_id)
    _persist()


# ── 音色菜单项工厂（避免闭包捕获问题）───────────────────
def _create_voice_item(name: str, vid: str) -> pystray.MenuItem:
    def action(_icon: object = None) -> None:
        _set_tts_voice(vid)
    def checked(_item: object = None) -> bool:
        return _tts_voice == vid
    return pystray.MenuItem(name, action, checked=checked)


def _build_menu() -> pystray.Menu:
    voice_items = [_create_voice_item(name, vid) for name, vid in VOICES.items()]
    return pystray.Menu(
        pystray.MenuItem("检测框", _toggle_overlay, checked=lambda _: _overlay_box_on),
        pystray.MenuItem("重置检测框", _reset_anchor),
        pystray.MenuItem("保存截图", _toggle_save, checked=lambda _: _save_screenshot_on),
        pystray.MenuItem("音色", pystray.Menu(*voice_items)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", lambda icon: (_stop_monitoring(), icon.stop())),
    )


# ── 区域计算 ──────────────────────────────────────────
def _discovery_bbox() -> tuple[int, int, int, int]:
    sw = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
    sh = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
    if CAPTURE_BOTTOM_RIGHT:
        return (sw // 2, sh // 2, sw, sh)
    return (0, 0, sw, sh)


def _anchor_bbox() -> tuple[int, int, int, int]:
    cx, cy = _anchor  # type: ignore[misc]
    return (cx - ANCHOR_CROP_W // 2, cy - ANCHOR_CROP_H // 2,
            cx + ANCHOR_CROP_W // 2, cy + ANCHOR_CROP_H // 2)


def _try_lock_anchor(matches: list[dict], offset: tuple[int, int]) -> bool:
    global _anchor
    if _anchor is not None:
        return True
    for m in matches:
        if m["confidence"] >= TEMPLATE_MATCH_THRESHOLD:
            x, y, w, h = m["rect"]
            sx, sy = x + offset[0], y + offset[1]
            cx, cy = sx + w // 2, sy + h // 2
            _anchor = (cx, cy)
            logger.info("锚点锁定: (%d, %d) 来自 %s", cx, cy, m["name"])
            return True
    return False


def _build_text(matches: list[dict]) -> str | None:
    matched_names = {m["name"] for m in matches}
    for tpl in _templates:
        if tpl.name in matched_names:
            text = TEMPLATE_TEXT_MAP.get(tpl.name)
            if text:
                return text
    return None


def _has_frame_changed(screen: "np.ndarray") -> bool:
    global _prev_md5
    md5 = hashlib.md5(screen.data).digest()  # type: ignore[arg-type]
    if _prev_md5 is not None and md5 == _prev_md5:
        return False
    _prev_md5 = md5
    return True


# ── 主循环 ────────────────────────────────────────────
def _capture_loop(stop_event: threading.Event) -> None:
    logger.info("识别循环已启动")
    global _last_text, _anchor, _save_dir, _save_seq
    skipped = 0
    matched = 0

    while not stop_event.is_set():
        try:
            # ── 1) 截图 ──
            bbox = _anchor_bbox() if _anchor else _discovery_bbox()
            if _overlay_box_on:
                show_overlay(bbox)
            screen = capture_screen(bbox=bbox)

            # ── 2) MD5 帧检测 ──
            if not _has_frame_changed(screen):
                skipped += 1
                stop_event.wait(CAPTURE_INTERVAL)
                continue

            # ── 2.5) 保存变化的截图 ──
            if _save_screenshot_on and _save_dir is not None:
                _save_seq += 1
                now = time.time()
                ms = int((now - int(now)) * 1_000_000)
                ts = f"{time.strftime('%H%M%S', time.localtime(now))}_{ms:06d}"
                label = "lock" if _anchor else "scan"
                fname = f"{ts}_{_save_seq:06d}_{label}.png"
                cv2.imwrite(str(_save_dir / fname), screen)

            # ── 3) 模板匹配 ──
            matched += 1
            matches = match_templates(screen, _templates)
            text = _build_text(matches)

            # ── 4) 锚点锁定 ──
            if _anchor is None:
                _try_lock_anchor(matches, (bbox[0], bbox[1]))
                stop_event.wait(CAPTURE_INTERVAL)
                continue

            # ── 5) 播报 ──
            if text and text != _last_text:
                speak(text, voice=_tts_voice)
                _last_text = text
            elif text is None and _last_text is not None:
                _last_text = None

        except Exception:
            logger.exception("识别循环异常")

        stop_event.wait(CAPTURE_INTERVAL)

    logger.info("识别循环已停止（匹配 %d 次，跳过 %d 帧）", matched, skipped)


# ── 启停 ──────────────────────────────────────────────
def _start_monitoring(*_args: object) -> None:
    global _running, _thread, _templates, _last_text, _anchor, _prev_md5
    if _running:
        return
    try:
        _templates = load_templates()
        logger.info("已加载 %d 个模板", len(_templates))
        for t in _templates:
            logger.info("  %s", t)
    except FileNotFoundError as exc:
        logger.error("模板加载失败：%s", exc)
        return
    _running = True
    _last_text = None
    _anchor = None
    _prev_md5 = None
    stop_event = threading.Event()
    _thread = threading.Thread(
        target=_capture_loop, args=(stop_event,), daemon=True, name="capture-loop"
    )
    _thread.stop_event = stop_event  # type: ignore[attr-defined]
    _thread.start()


def _stop_monitoring(*_args: object) -> None:
    global _running, _thread
    if not _running:
        return
    _running = False
    stop_event = getattr(_thread, "stop_event", None)
    if stop_event:
        stop_event.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout=3)
    _thread = None
    logger.info("已停止监控")


# ── 托盘入口 ──────────────────────────────────────────
def run_tray() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    _load_all_settings()

    icon_image = Image.open(Path(LOGO_PATH)) if Path(LOGO_PATH).is_file() else Image.new("RGBA", (64, 64), (0, 120, 215, 255))

    # 启动后如果之前开启了检测框则创建叠层
    if _overlay_box_on:
        create_overlay()

    menu = _build_menu()
    icon = pystray.Icon("yacht-opencv", icon_image, "游艇骰子 CV 助手", menu)

    _start_monitoring()
    logger.info("托盘应用已启动")
    icon.run()
    logger.info("托盘应用已退出")

    if _overlay_box_on:
        show_overlay(None)
        destroy_overlay()
