"""
core/downloader.py
────────────────────────────────────────────────────────────────────────────
yt-dlp 封装 —— 通过 subprocess 调用，下载 Bilibili/YouTube 等平台视频/音频
────────────────────────────────────────────────────────────────────────────
设计原则
  • 进程隔离：yt-dlp 以子进程形式运行，不污染主进程依赖
  • 进度回调：通过 yt-dlp 的 --progress-template 解析 JSON 进度
  • 错误处理：捕获子进程异常，通过 Signal 推送到 UI
  • 自动清理：下载完成后删除临时文件
"""

from __future__ import annotations

import os
import re
import json
import shlex
import logging
import subprocess
import time
import unicodedata
from pathlib import Path
from typing import Optional, List, Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, QProcess, QUrl

logger = logging.getLogger("Downloader")


# ─────────────────────────────────────────────────────────────────────────
# 数据结构：下载结果
# ─────────────────────────────────────────────────────────────────────────
@dataclass(slots=True)
class DownloadResult:
    """下载完成后返回的元信息"""
    success: bool
    file_path: Optional[str] = None      # 最终文件路径
    title: Optional[str] = None          # 视频标题
    duration_sec: Optional[float] = None # 时长（秒）
    error: Optional[str] = None          # 错误信息
    skipped: bool = False                # 文件已存在，跳过下载


# ─────────────────────────────────────────────────────────────────────────
# DownloaderWorker —— 在独立 QThread 中运行
# ─────────────────────────────────────────────────────────────────────────
class DownloaderWorker(QObject):
    """
    后台下载线程。

    Signals（跨线程安全）：
        progress_updated   → float  0.0-1.0
        download_finished  → DownloadResult
    """

    progress_updated = Signal(float)
    download_finished = Signal(object)   # DownloadResult

    # ── 构造函数 ──────────────────────────────────────────────────────────
    def __init__(
        self,
        output_dir: str,
        ffmpeg_path: Optional[str] = None,
        proxy: Optional[str] = None,
        parent=None,
    ):
        """
        :param output_dir:  下载输出目录
        :param ffmpeg_path: ffmpeg.exe 路径（None → 系统PATH）
        :param proxy:       代理地址，如 "http://127.0.0.1:7890"
        """
        super().__init__(parent)
        self.output_dir = output_dir
        self.ffmpeg_path = ffmpeg_path
        self.proxy = proxy

        self._process: Optional[subprocess.Popen] = None
        self._is_cancelled = False

    # ── 公开 API ──────────────────────────────────────────────────────────
    def download(
        self,
        url: str,
        format_id: Optional[str] = None,
        audio_only: bool = False,
    ) -> None:
        """
        触发异步下载。

        :param url:         视频链接（Bilibili/YouTube 等）
        :param format_id:   指定格式 ID（None → 自动选择最佳）
        :param audio_only:  True → 仅下载音频（m4a/mp3）
        """
        self._is_cancelled = False
        try:
            result = self._run_download(url, format_id, audio_only)
            self.download_finished.emit(result)
        except Exception as exc:
            logger.exception("下载失败")
            self.download_finished.emit(
                DownloadResult(success=False, error=str(exc))
            )

    def cancel(self) -> None:
        """取消当前下载"""
        self._is_cancelled = True
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            logger.info("下载已取消")

    # ── 核心下载逻辑 ──────────────────────────────────────────────────────
    def _run_download(
        self,
        url: str,
        format_id: Optional[str],
        audio_only: bool,
    ) -> DownloadResult:
        """
        分两阶段执行：
        1. yt-dlp --dump-json → 可靠获取 title / duration（不影响下载）
        2. yt-dlp 下载 → 通过 after_move_hook 把最终路径写入文件

        这样完全绕过 stdout 文本解析的歧义问题。
        """

        # ── 阶段 0：参数准备 ──────────────────────────────────────────────
        output_template = os.path.join(
            self.output_dir,
            "%(title).100s.%(ext)s",
        )

        if audio_only:
            format_selector = "bestaudio/best"
        elif format_id:
            format_selector = format_id
        else:
            # 视频：最佳 mp4 + 最佳 m4a 音频，自动合并
            format_selector = (
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]"
                "/best[ext=mp4]/best"
            )

        proxy_cmd = ["--proxy", self.proxy] if self.proxy else []

        # ── 阶段 1：获取元信息（--dump-json）──────────────────────────────
        info_cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-playlist",
            "--no-download",
            url,
            *proxy_cmd,
        ]
        logger.info("获取元信息: %s", shlex.join(info_cmd))

        info_proc = subprocess.run(
            info_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

        title = None
        duration_sec = None
        expected_ext = "m4a" if audio_only else "mp4"

        if info_proc.returncode == 0:
            try:
                info_data = json.loads(info_proc.stdout)
                title = info_data.get("title") or info_data.get("fulltitle")
                duration_sec = info_data.get("duration")
                # 根据实际可用格式推断扩展名
                if not audio_only:
                    for fmt in info_data.get("requested_formats", []):
                        if fmt.get("vcodec", "none") != "none":
                            expected_ext = fmt.get("ext", "mp4")
                            break
                    else:
                        # 没有合并格式，取 best 格式的 ext
                        best_ext = info_data.get("ext", "mp4")
                        if best_ext:
                            expected_ext = best_ext
                else:
                    for fmt in info_data.get("requested_formats", []):
                        if fmt.get("acodec", "none") != "none":
                            expected_ext = fmt.get("ext", "m4a")
                            break
                    best_ext = info_data.get("ext", "m4a")
                    if best_ext and best_ext != "mp4":
                        expected_ext = best_ext
                logger.info(
                    "元信息获取成功: title=%s, duration=%s, ext=%s",
                    title, duration_sec, expected_ext,
                )
            except json.JSONDecodeError as exc:
                logger.warning("JSON 解析失败: %s", exc)
        else:
            err = info_proc.stderr.strip()[:300]
            logger.warning("元信息获取失败（继续下载）: %s", err)

        # ── 检查文件是否已存在 ─────────────────────────────────────────
        if title:
            # yt-dlp 输出模板：%(title).100s.%(ext)s
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:100].strip()
            # 尝试多种可能扩展名
            possible_exts = [expected_ext]
            if expected_ext != "mp4":
                possible_exts.append("mp4")
            if expected_ext != "m4a":
                possible_exts.append("m4a")
            for ext in possible_exts:
                candidate = os.path.join(self.output_dir, f"{safe_title}.{ext}")
                if os.path.isfile(candidate):
                    logger.info("文件已存在，跳过下载: %s", candidate)
                    self.progress_updated.emit(1.0)
                    return DownloadResult(
                        success=True,
                        file_path=candidate,
                        title=title,
                        duration_sec=duration_sec,
                        skipped=True,
                    )

        # ── 阶段 2：下载文件 ──────────────────────────────────────────────
        filepath_file = os.path.join(self.output_dir, "_filepath.txt")

        download_cmd = [
            "yt-dlp",
            "--no-playlist",
            "--no-part",
            "-o", output_template,
            "-f", format_selector,
            "--newline",
            "--progress",
            "--progress-template",
            "%(progress._percent_str)s|%(progress._eta_str)s|%(progress._speed_str)s",
            "--print-to-file", "%(filepath)s", filepath_file,
            # 合并需要 ffmpeg
            *([] if not self.ffmpeg_path else ["--ffmpeg-location", self.ffmpeg_path]),
            *proxy_cmd,
            url,
        ]

        logger.info("执行命令: %s", shlex.join(download_cmd))

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        self._process = subprocess.Popen(
            download_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        # ── 解析进度（stdout）─────────────────────────────────────────────
        for line in self._process.stdout:
            if self._is_cancelled:
                break

            line = line.strip()
            if not line or "|" not in line or "%" not in line:
                continue

            try:
                parts = line.split("|")
                percent_str = parts[0].strip()
                match = re.search(r"(\d+\.?\d*)%", percent_str)
                if match:
                    percent = float(match.group(1)) / 100.0
                    self.progress_updated.emit(min(percent, 1.0))
            except (ValueError, IndexError):
                pass

        stderr = self._process.stderr.read() if self._process.stderr else ""
        if stderr:
            for line in stderr.strip().splitlines()[:10]:
                logger.debug("yt-dlp stderr: %s", line)

        return_code = self._process.wait()
        self._process = None

        if self._is_cancelled:
            return DownloadResult(success=False, error="下载已取消")

        if return_code != 0:
            # 提取关键错误行
            err_lines = [
                l.strip() for l in stderr.splitlines()
                if l.strip() and not l.startswith("[")
            ]
            err_msg = err_lines[0][:300] if err_lines else f"退出码 {return_code}"
            return DownloadResult(success=False, error=err_msg)

        # ── 读取文件路径（--print-to-file 写入）──────────────────────────
        filepath = None
        if os.path.exists(filepath_file):
            try:
                with open(filepath_file, "r", encoding="utf-8") as f:
                    filepath = f.read().strip()
                os.remove(filepath_file)
                logger.info("路径文件读取成功: %s", filepath)
            except Exception:
                pass

        # 回退：目录里找最新媒体文件（不限制时间，覆盖"文件已存在"场景）
        if not filepath:
            filepath = self._find_latest_file(self.output_dir)

        if not filepath:
            return DownloadResult(
                success=False,
                title=title,
                duration_sec=duration_sec,
                error="未找到下载文件（可能下载失败或文件被合并删除）",
            )

        logger.info("下载完成: %s", filepath)
        return DownloadResult(
            success=True,
            file_path=filepath,
            title=title,
            duration_sec=duration_sec,
        )

    def _find_latest_file(self, directory: str) -> Optional[str]:
        """在目录中找到最新的视频/音频文件"""
        extensions = {".mp4", ".mkv", ".webm", ".m4a", ".mp3", ".opus", ".flac"}
        try:
            files = [
                f for f in Path(directory).iterdir()
                if f.is_file() and f.suffix.lower() in extensions
            ]
            if files:
                latest = max(files, key=lambda f: f.stat().st_mtime)
                return str(latest.resolve())
        except Exception:
            pass
        return None


# ─────────────────────────────────────────────────────────────────────────
# 辅助函数：从 yt-dlp 提取信息（不下载）
# ─────────────────────────────────────────────────────────────────────────
def fetch_video_info(url: str, proxy: Optional[str] = None) -> dict:
    """
    获取视频元信息（标题、时长、可用格式），不下载。

    返回格式：
    {
        "title": str,
        "duration": float,
        "thumbnail": str,
        "formats": [{"format_id": str, "ext": str, "resolution": str, "note": str}]
    }
    """
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-playlist",
        url,
    ]
    if proxy:
        cmd.extend(["--proxy", proxy])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp 错误: {result.stderr}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON 解析失败: {exc}") from exc

    formats = []
    for fmt in data.get("formats", []):
        if fmt.get("vcodec") != "none" or fmt.get("acodec") != "none":
            formats.append({
                "format_id": fmt.get("format_id", ""),
                "ext": fmt.get("ext", ""),
                "resolution": fmt.get("resolution", ""),
                "filesize": fmt.get("filesize") or fmt.get("filesize_approx"),
                "vcodec": fmt.get("vcodec", "none"),
                "acodec": fmt.get("acodec", "none"),
            })

    return {
        "title": data.get("title", data.get("fulltitle", "未知标题")),
        "duration": data.get("duration", 0),
        "thumbnail": data.get("thumbnail", ""),
        "uploader": data.get("uploader", ""),
        "formats": formats,
    }


# ─────────────────────────────────────────────────────────────────────────
# 工具函数：文件名清理（移除非法字符）
# ─────────────────────────────────────────────────────────────────────────
def sanitize_filename(name: str, max_length: int = 200) -> str:
    """移除文件名中的非法字符"""
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = "".join(ch for ch in name if unicodedata.category(ch) != "Cc")
    if len(name) > max_length:
        name = name[:max_length]
    return name.strip() or "unnamed"
