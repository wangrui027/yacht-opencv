"""持久化配置 —— 保存/读取用户设置到 APPDATA。"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

SETTINGS_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "yacht-opencv"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

DEFAULT = {
    "tts_voice": "zh-CN-YunjianNeural",
    "overlay_box_on": False,
    "save_screenshot_on": False,
}

# 所有支持的音色 (显示名 → API 标识)
VOICES: dict[str, str] = {
    "晓晓": "zh-CN-XiaoxiaoNeural",
    "晓伊": "zh-CN-XiaoyiNeural",
    "云健": "zh-CN-YunjianNeural",
    "云希": "zh-CN-YunxiNeural",
    "云夏": "zh-CN-YunxiaNeural",
    "云扬": "zh-CN-YunyangNeural",
    "小蓓(东北话)": "zh-CN-liaoning-XiaobeiNeural",
    "小妮(陕西话)": "zh-CN-shaanxi-XiaoniNeural",
}


def load() -> dict:
    """从 settings.json 读取配置，失败则返回默认值。"""
    if not SETTINGS_FILE.exists():
        return dict(DEFAULT)
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        # 补全缺失的键
        result = dict(DEFAULT)
        result.update(data)
        return result
    except Exception as exc:
        logger.warning("读取配置文件失败: %s", exc)
        return dict(DEFAULT)


def save(data: dict) -> None:
    """写入 settings.json。"""
    try:
        payload = json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("保存配置失败，数据异常: %s  data=%s", exc, type(data))
        return
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(payload, encoding="utf-8")
    except Exception as exc:
        logger.warning("保存配置写入失败: %s", exc)
