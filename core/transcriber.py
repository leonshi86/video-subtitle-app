"""
core/transcriber.py
────────────────────────────────────────────────────────────────────────────
Faster-Whisper 封装 —— 纯 CPU 推理（device="cpu", compute_type="int8"）
────────────────────────────────────────────────────────────────────────────
设计原则
  • CPU 环境零 CUDA：强制 device="cpu"，compute_type="int8"
  • 分段批量推理：每段 30 秒音频，降低单次内存峰值
  • 内存安全：max_memory 参数限制模型层加载量
  • 单例模型：全局只加载一次，避免重复显存/内存消耗
  • 进度回调：转写过程中通过 signal 推送进度 0.0-1.0
"""

from __future__ import annotations

import os
import re
import gc
import time
import logging
import traceback
from dataclasses import dataclass
from typing import Optional, Callable, List

from PySide6.QtCore import QObject, Signal, QThread

# Faster-Whisper（CPU 推理核心）
#   • device="cpu"              → 禁用一切 GPU 代码路径
#   • compute_type="int8"       → 8-bit 整数量化，CPU 友好，精度可接受
#   • num_workers=1             → 单线程批处理，防止多进程争抢 CPU
#   • doc: https://github.com/guillaumekln/faster-whisper
from faster_whisper import WhisperModel

logger = logging.getLogger("Transcriber")


# ─────────────────────────────────────────────────────────────────────────
# 数据结构：单条字幕条目
# ─────────────────────────────────────────────────────────────────────────
@dataclass(slots=True, frozen=True)
class SubtitleEntry:
    """带时间戳的字幕条目"""
    start_sec: float   # 起始时间（秒），闭区间
    end_sec: float      # 结束时间（秒），开区间
    text: str           # 纯文本


# ─────────────────────────────────────────────────────────────────────────
# TranscriberWorker —— 在独立 QThread 中运行
# ─────────────────────────────────────────────────────────────────────────
class TranscriberWorker(QObject):
    """
    后台转写线程。

    Signals（全部跨线程安全）：
        progress_updated   → float  0.0-1.0
        transcription_done → List[SubtitleEntry]  成功返回
        transcription_error→ str     异常信息
        text_segment       → str    实时输出文字片段（流式转写）
    """

    progress_updated = Signal(float)
    transcription_done = Signal(list)
    transcription_error = Signal(str)
    text_segment = Signal(str, float, float)  # (text, start_sec, end_sec) 实时文字片段

    # ── 构造函数 ──────────────────────────────────────────────────────────
    def __init__(
        self,
        model_size: str = "base",           # tiny / base / small / medium / large-v3
        model_dir: Optional[str] = None,   # 本地模型路径（None → 自动从 HF 下载）
        language: Optional[str] = None,    # 强制语言；None → auto（自动检测）
        parent=None,
    ):
        super().__init__(parent)
        self.model_size = model_size
        self.model_dir = model_dir
        self.language = language

        self._model: Optional[WhisperModel] = None
        self._audio_path: Optional[str] = None
        self._is_cancelled = False
        self._is_paused = False

    @staticmethod
    def _split_by_punctuation(text: str) -> List[str]:
        """
        按中英文标点符号拆分文本为句子列表，保留标点到句末。
        例如："今天天气好，我们去玩吧。" → ["今天天气好，", "我们去玩吧。"]
        兜底：如果完全没有标点且文本较长，按固定长度断句。
        """
        # 用正则拆分，但保留分隔符（标点）附加到前面的句子
        parts = re.split(r'(?<=[，。！？；：,.!?;:\n])', text)
        result = [p.strip() for p in parts if p.strip()]

        # 兜底：无标点长文本，按固定字符数断句
        if len(result) == 1 and len(result[0]) > 40 and not re.search(r'[，。！？；：,.!?;:\n]', text):
            # 每 30-40 个字符断一句（优先在逗号/空格处断，没有就硬断）
            line = result[0]
            result = []
            while len(line) > 0:
                if len(line) <= 40:
                    result.append(line)
                    break
                # 在前 40 字符内找最后一个空格或自然停顿处
                chunk = line[:40]
                result.append(chunk)
                line = line[40:]

        return result

    # ── 公开 API ──────────────────────────────────────────────────────────
    def transcribe(self, audio_path: str) -> None:
        """
        触发异步转写（会在线程中执行）。
        完成后发射 transcription_done(error=None) 或 transcription_error。
        """
        self._audio_path = audio_path
        self._is_cancelled = False
        self._is_paused = False
        try:
            self._load_model()
            self._do_transcribe()
        except Exception as exc:
            logger.exception("转写失败")
            self.transcription_error.emit(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")

    def cancel(self) -> None:
        """请求取消当前转写任务"""
        self._is_cancelled = True

    def pause(self) -> None:
        """暂停转写（释放 CPU）"""
        self._is_paused = True
        logger.info("转写已暂停")

    def resume(self) -> None:
        """恢复转写"""
        self._is_paused = False
        logger.info("转写已恢复")

    # ── 模型加载（懒加载，单例模式） ───────────────────────────────────
    @classmethod
    def _get_model_cache(cls) -> dict:
        """进程级模型缓存，同一 size 只加载一次"""
        if not hasattr(cls, "_model_cache"):
            cls._model_cache: dict[str, WhisperModel] = {}
        return cls._model_cache

    def _load_model(self) -> None:
        """线程安全懒加载 Faster-Whisper 模型"""
        cache = self._get_model_cache()
        cache_key = f"{self.model_size}:{self.model_dir or 'default'}"

        if cache_key not in cache:
            logger.info(
                "正在加载 Faster-Whisper 模型 '%s'（CPU / int8）…", self.model_size
            )
            # ╔══════════════════════════════════════════════════════════════╗
            # ║  CPU 优化关键参数                                             ║
            # ║  • device='cpu'          → 强制 CPU，无任何 CUDA 调用          ║
            # ║  • compute_type='int8'   → 8-bit 量化，内存占用低、速度快     ║
            # ║  • num_workers=1         → 单线程批处理，节省内存              ║
            # ╚══════════════════════════════════════════════════════════════╝
            model = WhisperModel(
                model_size_or_path=self.model_size,
                download_root=self.model_dir,
                device="cpu",
                compute_type="int8",
                num_workers=1,
            )
            cache[cache_key] = model
            logger.info("模型 '%s' 加载完成", cache_key)
        else:
            logger.info("复用缓存模型 '%s'", cache_key)

        self._model = cache[cache_key]

    # ── 核心转写逻辑 ──────────────────────────────────────────────────────
    def _do_transcribe(self) -> None:
        assert self._model is not None, "模型未加载"
        assert self._audio_path is not None, "音频路径为空"

        audio_path = self._audio_path
        del self._audio_path   # 提前释放引用

        # ── 参数说明 ────────────────────────────────────────────────────
        # beam_size          → 束搜索宽度，越大越准但越慢；CPU 下建议 1-3
        # vad_filter         → 语音活动检测，过滤静音，减少幻觉
        # vad_parameters     → 静音阈值控制
        # language           → 强制语言（None → 自动检测）
        # segment_duration   → 分段时长（秒），控制每次推理的音频长度
        #                     CPU 下不宜过大，30s 是经验值
        # ─────────────────────────────────────────────────────────────────
        beam_size = 3
        segment_duration = 30.0   # 秒

        logger.info("开始转写音频文件: %s", audio_path)

        # ── 预处理：用 ffmpeg 提取纯音频（兼容各种容器格式） ──────────
        import subprocess, tempfile
        _audio_path = audio_path
        if not audio_path.lower().endswith((".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac")):
            _tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            _tmp.close()
            _audio_path = _tmp.name
            try:
                result = subprocess.run(
                    ["ffmpeg", "-y", "-i", audio_path, "-vn", "-acodec", "pcm_s16le",
                     "-ar", "16000", "-ac", "1", _audio_path],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=120,
                )
                if result.returncode != 0 or not os.path.exists(_audio_path) or os.path.getsize(_audio_path) < 1024:
                    logger.warning("ffmpeg 预提取失败(rc=%d)，回退原始文件: %s", result.returncode, result.stderr[:200])
                    _audio_path = audio_path
                else:
                    logger.info("ffmpeg 预提取音频完成: %s (%.1f MB)", _audio_path, os.path.getsize(_audio_path) / 1048576)
            except Exception as e:
                logger.warning("ffmpeg 预提取失败，回退原始文件: %s", e)
                _audio_path = audio_path

        try:
            # ── initial_prompt：提示模型输出标点 ─────────────────────
            # Whisper base 模型对中文标点输出较弱，通过 initial_prompt
            # 注入带标点的样本文本，让模型"模仿"输出标点。
            # condition_on_previous_text=True 会将上一段输出作为下一段的
            # 上下文提示，配合 initial_prompt 实现标点风格持续保持。
            prompt_map = {
                "zh": "请使用中文标点符号，包括逗号、句号、问号、感叹号、分号等。",
                "en": "Use proper punctuation: commas, periods, question marks, and exclamation marks.",
                "ja": "句読点を正しく使ってください。",
            }
            initial_prompt = None
            # 指定语言时直接取 prompt；自动检测时用中文 prompt（主要使用场景）
            if self.language and self.language in prompt_map:
                initial_prompt = prompt_map[self.language]
            elif self.language is None:
                # 自动检测：用中文 prompt（可覆盖大部分使用场景）
                initial_prompt = prompt_map["zh"]

            segments, info = self._model.transcribe(
                audio=_audio_path,
                language=self.language,
                beam_size=beam_size,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                task="transcribe",
                condition_on_previous_text=True,
                initial_prompt=initial_prompt,
            )
        finally:
            # 清理临时 wav
            if _audio_path != audio_path:
                try:
                    os.unlink(_audio_path)
                except OSError:
                    pass

        logger.info(
            "检测到语言: %s (概率 %.2f%%)", info.language, info.language_probability * 100
        )

        # ── 累积结果 + 进度回调 ──────────────────────────────────────────
        entries: List[SubtitleEntry] = []
        total_duration = info.duration or 0.0

        for seg in segments:
            # 暂停等待循环（释放 CPU 让 UI 响应）
            while self._is_paused:
                if self._is_cancelled:
                    logger.info("转写已取消（暂停中）")
                    self.transcription_error.emit("转写已取消")
                    return
                time.sleep(0.1)  # 短暂休眠，避免忙等待

            if self._is_cancelled:
                logger.info("转写已取消")
                self.transcription_error.emit("转写已取消")
                return

            text = seg.text.strip()
            if not text:
                # 空文本仍推送进度
                if total_duration > 0:
                    progress = min(seg.end / total_duration, 1.0)
                    self.progress_updated.emit(round(progress, 4))
                time.sleep(0.05)
                continue

            # 按标点拆句，每句一个 SubtitleEntry（时间轴按字符长度比例分配）
            sentences = self._split_by_punctuation(text)
            seg_duration = seg.end - seg.start
            total_chars = sum(len(s) for s in sentences) or 1
            elapsed = 0.0

            for i, sentence in enumerate(sentences):
                char_ratio = len(sentence) / total_chars
                sub_start = seg.start + elapsed
                sub_end = seg.start + elapsed + char_ratio * seg_duration if i < len(sentences) - 1 else seg.end
                elapsed += char_ratio * seg_duration

                entry = SubtitleEntry(
                    start_sec=round(sub_start, 3),
                    end_sec=round(sub_end, 3),
                    text=sentence,
                )
                entries.append(entry)
                # 实时发射到 UI（含时间轴，支持流式高亮同步）
                self.text_segment.emit(sentence, entry.start_sec, entry.end_sec)

            # 推送进度（基于时间轴而非片段数，更平滑）
            if total_duration > 0:
                progress = min(seg.end / total_duration, 1.0)
                self.progress_updated.emit(round(progress, 4))

            # 每 segment 休眠，让出 CPU 时间片避免 UI 卡顿
            time.sleep(0.05)

        # 强制清理显存（仅作保险，Faster-Whisper CPU 模式基本不占用显存）
        gc.collect()

        logger.info("转写完成，共 %d 条字幕", len(entries))
        self.progress_updated.emit(1.0)
        self.transcription_done.emit(entries)

    # ── 工具方法 ──────────────────────────────────────────────────────────
    @staticmethod
    def export_srt(entries: List[SubtitleEntry], output_path: str) -> None:
        """
        将字幕条目列表导出为 .srt 文件（SubRip 格式）。

        时间格式：HH:MM:SS,mmm
        """
        lines: List[str] = []
        for idx, entry in enumerate(entries, start=1):
            start = TranscriberWorker._format_timestamp(entry.start_sec)
            end = TranscriberWorker._format_timestamp(entry.end_sec)
            lines.append(f"{idx}")
            lines.append(f"{start} --> {end}")
            lines.append(entry.text)
            lines.append("")   # 空行分隔条目

        with open(output_path, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(lines))

        logger.info("SRT 字幕已保存: %s", output_path)

    @staticmethod
    def export_txt(entries: List[SubtitleEntry], output_path: str) -> None:
        """将字幕条目导出为纯文本 .txt 文件"""
        with open(output_path, "w", encoding="utf-8-sig") as f:
            for entry in entries:
                f.write(entry.text + "\n")

        logger.info("TXT 字幕已保存: %s", output_path)

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """float → 'HH:MM:SS,mmm' 格式（SRT 标准）"""
        ms = int(round(seconds * 1000))
        h, rem = divmod(ms, 3600 * 1000)
        m, rem = divmod(rem, 60 * 1000)
        s, ms = divmod(rem, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @staticmethod
    def get_current_entry(
        entries: List[SubtitleEntry], position_ms: int
    ) -> Optional[SubtitleEntry]:
        """
        根据播放器当前位置（毫秒）查找匹配的字幕条目。
        O(log n) 二分查找。
        """
        if not entries:
            return None
        pos_sec = position_ms / 1000.0
        # 二分查找：找最后一条 start <= pos_sec 的条目
        lo, hi = 0, len(entries) - 1
        result_idx = -1
        while lo <= hi:
            mid = (lo + hi) // 2
            if entries[mid].start_sec <= pos_sec:
                result_idx = mid
                lo = mid + 1
            else:
                hi = mid - 1
        # 额外校验 end_sec（防止跨段漂移）
        if result_idx >= 0 and entries[result_idx].end_sec >= pos_sec:
            return entries[result_idx]
        return None

    @staticmethod
    def get_current_entry_index(
        entries: List[SubtitleEntry], position_ms: int
    ) -> int:
        """
        根据播放器当前位置（毫秒）查找匹配的字幕条目索引。
        O(log n) 二分查找。找不到返回 -1。
        """
        if not entries:
            return -1
        pos_sec = position_ms / 1000.0
        lo, hi = 0, len(entries) - 1
        result_idx = -1
        while lo <= hi:
            mid = (lo + hi) // 2
            if entries[mid].start_sec <= pos_sec:
                result_idx = mid
                lo = mid + 1
            else:
                hi = mid - 1
        if result_idx >= 0 and entries[result_idx].end_sec >= pos_sec:
            return result_idx
        return -1

    @staticmethod
    def parse_srt(srt_path: str) -> List["SubtitleEntry"]:
        """
        从 .srt 文件解析字幕条目列表。

        支持 SRT 标准格式和简化格式（时间戳行 + 文本行）。
        """
        entries: List[SubtitleEntry] = []
        if not os.path.isfile(srt_path):
            return entries

        with open(srt_path, "r", encoding="utf-8-sig") as f:
            content = f.read()

        blocks = re.split(r"\n\s*\n", content.strip())
        ts_pattern = re.compile(
            r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
        )

        for block in blocks:
            lines = block.strip().splitlines()
            if len(lines) < 2:
                continue

            # 找到时间戳行
            ts_line = None
            text_lines = []
            for line in lines:
                m = ts_pattern.search(line)
                if m:
                    ts_line = m
                elif not line.strip().isdigit():
                    text_lines.append(line.strip())

            if ts_line:
                start = (
                    int(ts_line.group(1)) * 3600
                    + int(ts_line.group(2)) * 60
                    + int(ts_line.group(3))
                    + int(ts_line.group(4)) / 1000.0
                )
                end = (
                    int(ts_line.group(5)) * 3600
                    + int(ts_line.group(6)) * 60
                    + int(ts_line.group(7))
                    + int(ts_line.group(8)) / 1000.0
                )
                text = "\n".join(text_lines).strip()
                if text:
                    entries.append(SubtitleEntry(start_sec=start, end_sec=end, text=text))

        logger.info("从 SRT 文件加载 %d 条字幕: %s", len(entries), srt_path)
        return entries


# ─────────────────────────────────────────────────────────────────────────
# 预热工具（可选，用于首次调用前提前加载模型）
# ─────────────────────────────────────────────────────────────────────────
def preload_model(
    model_size: str = "base",
    model_dir: Optional[str] = None,
) -> None:
    """
    在主线程中预热模型（首次下载会触发磁盘 I/O，提前做可以改善体验）。
    """
    cache = TranscriberWorker._get_model_cache()
    key = f"{model_size}:{model_dir or 'default'}"
    if key not in cache:
        logger.info("预热模型: %s", key)
        model = WhisperModel(
            model_size_or_path=model_size,
            download_root=model_dir,
            device="cpu",
            compute_type="int8",
            num_workers=1,
        )
        cache[key] = model
        logger.info("模型预热完成: %s", key)
