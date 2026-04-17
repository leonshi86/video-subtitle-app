"""
core/utils.py
────────────────────────────────────────────────────────────────────────────
通用工具函数
────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import shutil
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("Utils")


def check_ffmpeg() -> bool:
    """
    检查 FFmpeg 是否已安装并可用。

    Returns:
        True 如果 ffmpeg 在系统 PATH 中可用
    """
    # shutil.which 会在 PATH 中查找可执行文件
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        logger.info("FFmpeg 已安装: %s", ffmpeg_path)
        return True

    logger.warning("FFmpeg 未找到，请安装并添加到系统 PATH")
    return False


def get_ffmpeg_path() -> Optional[str]:
    """获取 FFmpeg 可执行文件路径"""
    return shutil.which("ffmpeg")


def ensure_dir(path: str) -> str:
    """确保目录存在，不存在则创建"""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def get_app_data_dir() -> str:
    """获取应用数据目录（用于存储模型等）"""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/.local/share")

    app_dir = Path(base) / "VideoSubtitleApp"
    app_dir.mkdir(parents=True, exist_ok=True)
    return str(app_dir)


def format_filesize(size_bytes: int) -> str:
    """格式化文件大小（人类可读）"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def format_duration(seconds: float) -> str:
    """格式化时长（HH:MM:SS）"""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
