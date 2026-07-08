"""语音通知 —— 调用本地 MP3 服务端播放 TTS。"""

from __future__ import annotations

import logging
import urllib.parse

import requests

from yacht_opencv.config import MP3_SERVER_URL, MP3_TIMEOUT

logger = logging.getLogger(__name__)


def speak(text: str, /, *, voice: str) -> bool:
    """调用 MP3 服务端播报文本。

    参数
    ----------
    text : 要播报的中文文本
    voice : TTS 语音名称（默认 zh-CN-YunxiNeural）

    返回
    -------
    是否成功调用（True = 服务端已接受请求）
    """
    params = urllib.parse.urlencode({"text": text, "voice": voice})
    url = f"{MP3_SERVER_URL}?{params}"

    try:
        resp = requests.get(url, timeout=MP3_TIMEOUT)
        resp.raise_for_status()
        logger.info("播报「%s」 → %s", text, resp.status_code)
        return True
    except requests.ConnectionError:
        logger.warning("MP3 服务未启动：%s", MP3_SERVER_URL)
    except requests.Timeout:
        logger.warning("MP3 服务超时：%s", MP3_SERVER_URL)
    except requests.RequestException as exc:
        logger.warning("MP3 调用失败：%s", exc)
    return False
