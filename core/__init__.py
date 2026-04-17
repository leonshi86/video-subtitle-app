"""
core/__init__.py
────────────────────────────────────────────────────────────────────────────
核心模块导出
────────────────────────────────────────────────────────────────────────────
"""

from .downloader import (
    DownloaderWorker,
    DownloadResult,
    fetch_video_info,
    sanitize_filename,
)

from .transcriber import (
    TranscriberWorker,
    SubtitleEntry,
    preload_model,
)

from .utils import (
    check_ffmpeg,
    get_ffmpeg_path,
    ensure_dir,
    get_app_data_dir,
    format_filesize,
    format_duration,
)

__all__ = [
    # 下载器
    "DownloaderWorker",
    "DownloadResult",
    "fetch_video_info",
    "sanitize_filename",
    # 转写器
    "TranscriberWorker",
    "SubtitleEntry",
    "preload_model",
    # 工具
    "check_ffmpeg",
    "get_ffmpeg_path",
    "ensure_dir",
    "get_app_data_dir",
    "format_filesize",
    "format_duration",
]
