"""语音通知 —— edge-tts 生成 + 本地缓存 + pygame 播放。"""

from __future__ import annotations

import asyncio
import logging
import shutil
import threading
import time
from pathlib import Path

import edge_tts
import pygame

logger = logging.getLogger(__name__)

# 缓存根目录（项目根目录下的 temp 文件夹）
_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "temp"

# pygame 混音器（只初始化一次）
_MIXER_INITED = False


def _ensure_mixer() -> None:
    global _MIXER_INITED
    if not _MIXER_INITED:
        try:
            pygame.mixer.init(frequency=24000, size=-16, channels=1)
            _MIXER_INITED = True
        except Exception as exc:
            logger.warning("pygame 混音器初始化失败: %s", exc)


def _cache_path(text: str, voice: str) -> Path:
    """获取缓存文件路径 temp/<voice>/<text>.mp3。"""
    # Windows 文件名不能含的字符替换掉
    safe_text = text.translate(str.maketrans({
        "\\": "_", "/": "_", ":": "_", "*": "_",
        "?": "_", "\"": "_", "<": "_", ">": "_", "|": "_",
    }))
    return _CACHE_DIR / voice / f"{safe_text}.mp3"


async def _generate(text: str, voice: str, output: str) -> bool:
    """调用 edge-tts 生成音频并保存到文件。"""
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output)
        logger.info("TTS 已缓存: %s", output)
        return True
    except Exception as exc:
        logger.warning("TTS 生成失败: %s", exc)
        return False


def _play_file(path: str) -> None:
    """播放 MP3 文件（阻塞直到播完或失败）。"""
    _ensure_mixer()
    try:
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        # 等待播放完成（最多等 5 秒防止死锁）
        deadline = time.monotonic() + 5
        while pygame.mixer.music.get_busy() and time.monotonic() < deadline:
            time.sleep(0.05)
    except Exception as exc:
        logger.warning("音频播放失败: %s", exc)


def speak(text: str, /, *, voice: str) -> bool:
    """播报文本（后台生成 + 播放，不阻塞调用者）。

    返回 True 表示已加入播放队列（不一定已播完）。
    """
    cache = _cache_path(text, voice)
    cached = cache.exists()

    if not cached:
        # 缓存不存在 → 生成
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        ok = asyncio.run(_generate(text, voice, str(cache)))
        if not ok:
            return False

    # 后台线程播放
    threading.Thread(target=_play_file, args=(str(cache),), daemon=True).start()
    return True


def clear_cache() -> None:
    """清空所有 TTS 缓存音频。"""
    if _CACHE_DIR.is_dir():
        try:
            shutil.rmtree(_CACHE_DIR)
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            logger.info("TTS 缓存已清空")
        except Exception as exc:
            logger.warning("清除缓存失败: %s", exc)
