"""
gui/main_window.py
────────────────────────────────────────────────────────────────────────────
主界面 —— PySide6 实现，包含下载、播放、字幕同步、导出功能
────────────────────────────────────────────────────────────────────────────
架构说明
  • 主线程：GUI 渲染、视频播放、字幕显示
  • 后台线程：DownloadWorker / TranscriberWorker
  • 通信机制：Signal / Slot 实现跨线程安全通信
"""

from __future__ import annotations

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Optional, List

from PySide6.QtCore import (
    Qt,
    QThread,
    QTimer,
    QUrl,
    Signal,
    Slot,
    QSize,
)
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QSplitter,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QSlider,
)
from PySide6.QtGui import QFont, QColor, QAction, QIcon, QDesktopServices
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

# 导入核心模块
sys.path.insert(0, str(Path(__file__).parent.parent))
from core import (
    DownloaderWorker,
    DownloadResult,
    TranscriberWorker,
    SubtitleEntry,
    fetch_video_info,
    preload_model,
)

# ── 日志配置 ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("MainWindow")

# ─────────────────────────────────────────────────────────────────────────
# 主窗口类
# ─────────────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    """
    主窗口，包含：
      • URL 输入与下载控制
      • 视频播放器（QMediaPlayer + QVideoWidget）
      • 字幕显示区
      • 导出按钮（SRT / TXT）
    """

    # ── 初始化 ────────────────────────────────────────────────────────────
    def __init__(self):
        super().__init__()

        # ── 状态变量 ──────────────────────────────────────────────────────
        self._drag_pos = None  # 标题栏拖拽位置
        self._current_video_path: Optional[str] = None
        self._pending_video_path: Optional[str] = None
        self._subtitle_entries: List[SubtitleEntry] = []
        self._current_subtitle_index: int = -1  # 当前高亮的字幕行号，-1 表示无
        self._download_worker: Optional[DownloaderWorker] = None
        self._transcribe_worker: Optional[TranscriberWorker] = None
        self._download_thread: Optional[QThread] = None
        self._transcribe_thread: Optional[QThread] = None
        self._auto_play_pending: bool = False
        self._video_history: List[dict] = []  # 视频历史记录

        # ── 基础配置 ──────────────────────────────────────────────────────
        self.setWindowTitle("视频字幕工具 v1.0")
        self.setMinimumSize(1100, 750)
        self.resize(1280, 820)
        
        # 无边框窗口 + 自定义标题栏
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # ── 全局深色主题样式 ──────────────────────────────────────────────
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #FFFFFF;
                color: #1E3A5F;
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
            }
            QLabel {
                color: #1E3A5F;
                background: transparent;
            }
            QLineEdit {
                background-color: #FFFFFF;
                border: 1px solid #BBDEFB;
                border-radius: 6px;
                padding: 8px 12px;
                color: #1E3A5F;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #0078D4;
            }
            QLineEdit::placeholder {
                color: #5D7A9C;
            }
            QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #BBDEFB;
                border-radius: 6px;
                padding: 6px 12px;
                color: #1E3A5F;
                font-size: 13px;
                min-width: 80px;
            }
            QComboBox:hover {
                border-color: #484F58;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #8B949E;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                border: 1px solid #BBDEFB;
                selection-background-color: #0078D4;
                color: #1E3A5F;
            }
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #BBDEFB;
                border-radius: 6px;
                padding: 6px 16px;
                color: #1E3A5F;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #BBDEFB;
                border-color: #484F58;
            }
            QPushButton:pressed {
                background-color: #FFFFFF;
            }
            QPushButton:disabled {
                background-color: #FFFFFF;
                color: #484F58;
                border-color: #FFFFFF;
            }
            QProgressBar {
                background-color: #FFFFFF;
                border: 1px solid #BBDEFB;
                border-radius: 4px;
                height: 8px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #0078D4;
                border-radius: 3px;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #FFFFFF;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #0078D4;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #0078D4;
                border-radius: 2px;
            }
            QScrollBar:vertical {
                background: #FFFFFF;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #BBDEFB;
                min-height: 30px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #484F58;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QSplitter::handle {
                background: #FFFFFF;
            }
        """)

        # ── 初始化 UI ──────────────────────────────────────────────────────
        self._setup_ui()
        self._setup_media_player()
        self._connect_signals()

        # ── 预热模型（可选，首次启动会下载模型） ──────────────────────────
        # QTimer.singleShot(500, lambda: preload_model("base"))

        # ── 加载历史记录 ──────────────────────────────────────────────────
        self._load_history()

        logger.info("主窗口初始化完成")

    # ── UI 布局 ────────────────────────────────────────────────────────────
    def _setup_ui(self) -> None:
        """构建主界面布局 - 深色科技风格"""

        # ── 中央 Widget ───────────────────────────────────────────────────
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(0)
        # 浅蓝渐变背景
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setBrush(self.backgroundRole(), QColor(245, 249, 255))
        self.setPalette(p)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ════════════════════════════════════════════════════════════════
        # 自定义标题栏
        # ════════════════════════════════════════════════════════════════
        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet("background-color: #FFFFFF; border-bottom: 1px solid #FFFFFF;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(12, 0, 8, 0)

        # 标题
        title_label = QLabel("视频字幕工具 v1.0")
        title_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #1E3A5F; background: transparent;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        # 窗口控制按钮
        btn_min = QPushButton("─")
        btn_min.setFixedSize(46, 40)
        btn_min.setStyleSheet("""
            QPushButton { background: transparent; border: none; color: #5D7A9C; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background: #FFFFFF; color: #1E3A5F; }
        """)
        btn_min.clicked.connect(self.showMinimized)
        title_layout.addWidget(btn_min)

        btn_max = QPushButton("□")
        btn_max.setFixedSize(46, 40)
        btn_max.setStyleSheet("""
            QPushButton { background: transparent; border: none; color: #5D7A9C; font-size: 14px; }
            QPushButton:hover { background: #FFFFFF; color: #1E3A5F; }
        """)
        btn_max.clicked.connect(self._toggle_maximize)
        title_layout.addWidget(btn_max)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(46, 40)
        btn_close.setStyleSheet("""
            QPushButton { background: transparent; border: none; color: #5D7A9C; font-size: 14px; }
            QPushButton:hover { background: #DA3633; color: #FFFFFF; }
        """)
        btn_close.clicked.connect(self.close)
        title_layout.addWidget(btn_close)

        main_layout.addWidget(title_bar)

        # ════════════════════════════════════════════════════════════════
        # 下载控制栏
        # ════════════════════════════════════════════════════════════════
        download_bar = QWidget()
        download_bar.setStyleSheet("background-color: #FFFFFF; border-bottom: 1px solid #FFFFFF;")
        download_layout = QHBoxLayout(download_bar)
        download_layout.setContentsMargins(16, 12, 16, 12)
        download_layout.setSpacing(12)

        # URL 输入框
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("粘贴视频链接（Bilibili / YouTube 等）")
        self.url_input.setClearButtonEnabled(True)
        self.url_input.setMinimumHeight(36)
        download_layout.addWidget(self.url_input, stretch=4)

        # 下载类型选择
        self.format_combo = QComboBox()
        self.format_combo.addItems(["视频", "仅音频"])
        self.format_combo.setFixedHeight(36)
        download_layout.addWidget(self.format_combo)

        # 下载按钮 - 蓝色主操作按钮
        self.download_btn = QPushButton("下载")
        self.download_btn.setFixedSize(100, 36)
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D4;
                border: none;
                border-radius: 6px;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #106EBE;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
            QPushButton:disabled {
                background-color: #FFFFFF;
                color: #484F58;
            }
        """)
        download_layout.addWidget(self.download_btn)

        # 进度条
        self.download_progress = QProgressBar()
        self.download_progress.setFixedSize(180, 8)
        self.download_progress.setTextVisible(False)
        download_layout.addWidget(self.download_progress)

        main_layout.addWidget(download_bar)

        # ════════════════════════════════════════════════════════════════
        # 主内容区：左侧历史 + 右侧播放/字幕
        # ════════════════════════════════════════════════════════════════
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.setStyleSheet("QSplitter::handle { width: 1px; background: #FFFFFF; }")

        # ── 左侧：历史记录 ───────────────────────────────────────────────
        history_panel = QWidget()
        history_panel.setStyleSheet("background-color: #FFFFFF;")
        history_layout = QVBoxLayout(history_panel)
        history_layout.setContentsMargins(12, 12, 12, 12)
        history_layout.setSpacing(8)

        # 标题
        history_header = QLabel("📁 历史记录")
        history_header.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        history_header.setStyleSheet("color: #1E3A5F; padding: 4px 0;")
        history_layout.addWidget(history_header)

        # 列表
        self.history_list = QListWidget()
        self.history_list.setMinimumWidth(200)
        self.history_list.setMaximumWidth(280)
        self.history_list.setStyleSheet("""
            QListWidget {
                background-color: #FFFFFF;
                border: 1px solid #FFFFFF;
                border-radius: 6px;
                font-size: 12px;
                outline: none;
            }
            QListWidget::item {
                color: #5D7A9C;
                padding: 10px 10px;
                border-bottom: 1px solid #FFFFFF;
            }
            QListWidget::item:selected {
                background-color: #FFFFFF;
                color: #1E3A5F;
            }
            QListWidget::item:hover {
                background-color: #FFFFFF;
            }
        """)
        history_layout.addWidget(self.history_list, stretch=1)

        # 清空按钮
        self.history_clear_btn = QPushButton("清空记录")
        self.history_clear_btn.setFixedHeight(32)
        self.history_clear_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #BBDEFB;
                border-radius: 6px;
                color: #5D7A9C;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #DA3633;
                border-color: #DA3633;
                color: #FFFFFF;
            }
        """)
        history_layout.addWidget(self.history_clear_btn)

        content_splitter.addWidget(history_panel)

        # ── 右侧：视频播放区 + 字幕显示 ────────────────────────────────
        right_panel = QWidget()
        right_panel.setStyleSheet("background-color: #FFFFFF;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(12)

        # 视频容器（包含视频画面 + 控制栏）
        video_container = QWidget()
        video_container.setStyleSheet("background-color: #000000; border-radius: 8px;")
        video_container.setMinimumHeight(220)  # 确保控制栏始终可见
        video_container_layout = QVBoxLayout(video_container)
        video_container_layout.setContentsMargins(0, 0, 0, 0)
        video_container_layout.setSpacing(0)

        # 加载提示
        self.loading_label = QLabel("⏳ 加载中...")
        self.loading_label.setFixedSize(160, 40)
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 200);
                color: #0078D4;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
            }
        """)
        self.loading_label.setVisible(False)
        self._loading_dots = 0
        self._loading_timer = QTimer(self)
        self._loading_timer.timeout.connect(self._update_loading_text)

        # 视频播放控件 - 不设最小高度，让布局自动分配空间
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000;")

        # 视频栈布局（用于叠加 loading_label 和字幕）
        self._video_stack = QWidget()
        self._video_stack.setMinimumHeight(150)  # 允许更小的最小高度
        self._video_stack_layout = QVBoxLayout(self._video_stack)
        self._video_stack_layout.setContentsMargins(0, 0, 0, 0)
        self._video_stack_layout.addWidget(self.video_widget)
        self.loading_label.setParent(self._video_stack)
        video_container_layout.addWidget(self._video_stack, stretch=1)

        # ── 播放控制栏（放在 video_container 内部）────────────────────────
        control_bar = QWidget()
        control_bar.setStyleSheet("""
            background-color: #FFFFFF;
            border-top: 1px solid #FFFFFF;
        """)
        control_layout = QHBoxLayout(control_bar)
        control_layout.setContentsMargins(12, 8, 12, 8)
        control_layout.setSpacing(12)

        # 播放/停止按钮
        self.play_btn = QPushButton("▶ 播放")
        self.play_btn.setFixedSize(90, 32)
        self.play_btn.setEnabled(False)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #BBDEFB;
                border-radius: 6px;
                color: #1E3A5F;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #BBDEFB; }
            QPushButton:disabled {
                background-color: #FFFFFF;
                color: #484F58;
                border-color: #FFFFFF;
            }
        """)
        control_layout.addWidget(self.play_btn)

        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setFixedSize(90, 32)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(self.play_btn.styleSheet())
        control_layout.addWidget(self.stop_btn)

        # 进度条
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.setEnabled(False)
        self.position_slider.setFixedHeight(20)
        control_layout.addWidget(self.position_slider, stretch=1)

        # 时间标签
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setFixedWidth(110)
        self.time_label.setStyleSheet("color: #5D7A9C; font-size: 12px;")
        control_layout.addWidget(self.time_label)

        video_container_layout.addWidget(control_bar)

        # ── 当前字幕标签（叠加在视频上）──────────────────────────────
        self.current_subtitle_label = QLabel("")
        self.current_subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_subtitle_label.setFont(QFont("Microsoft YaHei", 15, QFont.Weight.Bold))
        self.current_subtitle_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 180);
                color: #FFFFFF;
                border-radius: 6px;
                padding: 8px 16px;
            }
        """)
        self.current_subtitle_label.setWordWrap(True)
        self.current_subtitle_label.setVisible(False)
        self.current_subtitle_label.setParent(self._video_stack)

        # 视频容器优先获取空间，字幕区限制最大高度
        right_layout.addWidget(video_container, stretch=4)

        # ── 字幕显示区 ────────────────────────────────────────────────
        subtitle_panel = QWidget()
        subtitle_panel.setStyleSheet("""
            background-color: #FFFFFF;
            border: 1px solid #FFFFFF;
            border-radius: 8px;
        """)
        subtitle_layout = QVBoxLayout(subtitle_panel)
        subtitle_layout.setContentsMargins(12, 10, 12, 10)
        subtitle_layout.setSpacing(8)

        # 标题
        subtitle_header = QLabel("语音识别")
        subtitle_header.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        subtitle_header.setStyleSheet("color: #1E3A5F;")
        subtitle_layout.addWidget(subtitle_header)

        # 字幕列表
        self.subtitle_display = QListWidget()
        self.subtitle_display.setFont(QFont("Microsoft YaHei", 13))
        self.subtitle_display.setStyleSheet("""
            QListWidget {
                background-color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 4px;
                outline: none;
            }
            QListWidget::item {
                color: #5D7A9C;
                padding: 4px 10px;
                border-bottom: 1px solid #FFFFFF;
            }
            QListWidget::item:active { background: transparent; }
        """)
        self.subtitle_display.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.subtitle_display.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.subtitle_display.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.subtitle_display.setMaximumHeight(200)
        subtitle_layout.addWidget(self.subtitle_display)

        # 转写进度
        self.transcribe_progress = QProgressBar()
        self.transcribe_progress.setFormat("转写进度: %p%")
        self.transcribe_progress.setVisible(False)
        self.transcribe_progress.setFixedHeight(6)
        subtitle_layout.addWidget(self.transcribe_progress)

        right_layout.addWidget(subtitle_panel)
        content_splitter.addWidget(right_panel)
        content_splitter.setSizes([240, 900])

        main_layout.addWidget(content_splitter, stretch=1)

        # ════════════════════════════════════════════════════════════════
        # 底部状态栏
        # ════════════════════════════════════════════════════════════════
        status_bar = QWidget()
        status_bar.setStyleSheet("background-color: #FFFFFF; border-top: 1px solid #FFFFFF;")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(16, 10, 16, 10)
        status_layout.setSpacing(12)

        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #5D7A9C; font-size: 12px;")
        status_layout.addWidget(self.status_label, stretch=1)

        # 导出按钮
        self.export_srt_btn = QPushButton("导出 SRT")
        self.export_srt_btn.setEnabled(False)
        self.export_srt_btn.setFixedHeight(32)
        self.export_srt_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                border: none;
                border-radius: 6px;
                color: #FFFFFF;
                font-size: 12px;
                font-weight: 600;
                padding: 0 16px;
            }
            QPushButton:hover { background-color: #2EA043; }
            QPushButton:disabled {
                background-color: #FFFFFF;
                color: #484F58;
            }
        """)
        status_layout.addWidget(self.export_srt_btn)

        self.export_txt_btn = QPushButton("导出 TXT")
        self.export_txt_btn.setEnabled(False)
        self.export_txt_btn.setFixedHeight(32)
        self.export_txt_btn.setStyleSheet(self.export_srt_btn.styleSheet())
        status_layout.addWidget(self.export_txt_btn)

        main_layout.addWidget(status_bar)

    def _toggle_maximize(self) -> None:
        """切换窗口最大化状态"""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def mousePressEvent(self, event) -> None:
        """标题栏拖拽"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """标题栏拖拽移动"""
        if hasattr(self, '_drag_pos') and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """结束拖拽"""
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    # ── 媒体播放器初始化 ───────────────────────────────────────────────────
    def _setup_media_player(self) -> None:
        """初始化 QMediaPlayer 和音频输出"""

        # 注：禁用硬件解码的环境变量 QT_MULTIMEDIA_PREFER_SOFTWARE=1
        # 已在 main.py 的 QApplication 创建前设置，此处无需重复。

        # 音频输出（Qt 6.2+ 必需）
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0.8)

        # 媒体播放器

        # 错误处理

    # ── 信号连接 ───────────────────────────────────────────────────────────
    def _connect_signals(self) -> None:
        """连接 UI 信号槽"""

        # 下载
        self.download_btn.clicked.connect(self._start_download)
        self.url_input.returnPressed.connect(self._start_download)

        # 播放控制
        self.play_btn.clicked.connect(self._toggle_playback)
        self.stop_btn.clicked.connect(self._stop_playback)
        self.position_slider.sliderMoved.connect(self._seek_position)

        # 播放器状态变化

        # 导出
        self.export_srt_btn.clicked.connect(self._export_srt)
        self.export_txt_btn.clicked.connect(self._export_txt)

        # 历史列表
        self.history_list.itemDoubleClicked.connect(self._on_history_item_double_clicked)
        self.history_clear_btn.clicked.connect(self._on_history_clear)

    # ── 下载逻辑 ───────────────────────────────────────────────────────────
    @Slot()
    def _start_download(self) -> None:
        """启动下载任务（已存在则跳过，直接加载）"""

        # ── 防重复点击：上一次下载还在跑，禁止新建 ──
        if self._download_thread and self._download_thread.isRunning():
            self.status_label.setText("⏳ 正在下载中，请等待完成…")
            return

        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请输入视频链接")
            return

        audio_only = self.format_combo.currentIndex() == 1

        self.download_btn.setEnabled(False)
        self.download_progress.setValue(0)
        self.status_label.setText("正在获取视频信息…")

        # 后台下载
        self._download_thread = QThread()
        self._download_worker = DownloaderWorker(
            output_dir=self._get_download_dir(),
            ffmpeg_path=self._get_ffmpeg_path(),
        )
        self._download_worker.moveToThread(self._download_thread)

        self._download_worker.progress_updated.connect(self._on_download_progress)
        self._download_worker.download_finished.connect(self._on_download_finished)
        self._download_thread.started.connect(
            lambda: self._download_worker.download(url, audio_only=audio_only)
        )
        self._download_thread.start()

    @Slot(float)
    def _on_download_progress(self, progress: float) -> None:
        """更新下载进度"""
        pct = int(progress * 100)
        self.download_progress.setValue(pct)
        self.status_label.setText(f"正在下载… {pct}%")

    @Slot(object)
    def _on_download_finished(self, result: DownloadResult) -> None:
        """下载完成回调（跨线程安全：UI操作全部通过 QTimer.singleShot 推送到主线程）"""

        # 下载结果快照（用于跨线程传递，不持有 worker 引用）
        success = result.success
        file_path = result.file_path
        title = result.title or os.path.basename(result.file_path) if result.file_path else ""
        duration = result.duration_sec or 0
        error = result.error
        skipped = result.skipped

        # ── 所有 UI + 线程清理操作推送到主线程，避免在下载线程中 quit/wait 导致死锁 ──
        def ui_update():
            # 线程清理放在主线程：安全 quit + wait
            if self._download_thread:
                self._download_thread.quit()
                self._download_thread.wait(3000)
                self._download_thread = None
                self._download_worker = None

            self.download_btn.setEnabled(True)

            if not success:
                self.status_label.setText("下载失败")
                QMessageBox.critical(self, "下载失败", error or "未知错误")
                return

            self._current_video_path = file_path
            self._download_title = title
            self._download_duration = duration

            # 文件已存在提示
            if skipped:
                self.status_label.setText(f"文件已存在: {title}")
                QMessageBox.information(
                    self, "文件已存在",
                    f"本地已有该视频，已直接加载：\n{file_path}"
                )
            else:
                self.status_label.setText(f"下载完成: {title}（点击播放按钮开始）")

            self.play_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.position_slider.setEnabled(False)

            # 添加到历史记录（容错）
            try:
                self._add_to_history(title=title, file_path=file_path, duration=duration)
            except Exception as exc:
                logger.warning("添加历史记录失败: %s", exc)

            # 自动检测字幕：已有 SRT 则加载，否则开始转写
            srt_path = os.path.splitext(file_path)[0] + ".srt"
            if os.path.isfile(srt_path):
                try:
                    self._subtitle_entries = TranscriberWorker.parse_srt(srt_path)
                    self.status_label.setText(
                        f"下载完成，已加载已有字幕（{len(self._subtitle_entries)} 条）"
                    )
                    self.export_srt_btn.setEnabled(True)
                    self.export_txt_btn.setEnabled(True)
                    if self._subtitle_entries:
                        self._populate_subtitle_list()
                except Exception as exc:
                    logger.warning("加载已有字幕失败: %s", exc)
                    self._start_transcribe(file_path)
            else:
                # 本地已有字幕则跳过转写，否则开始转写
                self._start_transcribe(file_path)

        QTimer.singleShot(0, ui_update)

    # ── 转写逻辑 ───────────────────────────────────────────────────────────
    def _start_transcribe(self, audio_path: str) -> None:
        """启动后台转写"""

        self.transcribe_progress.setVisible(True)
        self.transcribe_progress.setValue(0)
        self.status_label.setText("正在转写（CPU 模式）…")

        # 清空字幕显示区，准备实时输出
        self.subtitle_display.clear()
        self._current_subtitle_index = -1

        # 创建后台线程（language=None → 自动检测）
        self._transcribe_thread = QThread()
        self._transcribe_worker = TranscriberWorker(
            model_size="base",  # CPU 推荐 base / small
            language=None,      # 自动检测语言
        )
        self._transcribe_worker.moveToThread(self._transcribe_thread)

        # 连接信号
        self._transcribe_worker.progress_updated.connect(
            lambda p: self.transcribe_progress.setValue(int(p * 100))
        )
        self._transcribe_worker.transcription_done.connect(self._on_transcribe_done)
        self._transcribe_worker.transcription_error.connect(self._on_transcribe_error)
        # 新增：实时文字输出
        self._transcribe_worker.text_segment.connect(self._on_text_segment)
        self._transcribe_thread.started.connect(
            lambda: self._transcribe_worker.transcribe(audio_path)
        )

        # 降低转写线程优先级，避免卡住 UI
        thread = self._transcribe_thread  # 局部捕获，避免 lambda 执行时 self._transcribe_thread 已被清理
        self._transcribe_thread.started.connect(
            lambda: thread.setPriority(QThread.Priority.LowPriority)
        )

        self._transcribe_thread.start()

    @Slot(str)
    def _on_text_segment(self, text: str) -> None:
        """实时追加文字到字幕显示区"""
        item = QListWidgetItem(text)
        self.subtitle_display.addItem(item)
        self.subtitle_display.scrollToItem(
            item, QAbstractItemView.ScrollHint.PositionAtBottom
        )

    @Slot(list)
    def _on_transcribe_done(self, entries: List[SubtitleEntry]) -> None:
        """转写完成"""

        # 清理线程
        if self._transcribe_thread:
            self._transcribe_thread.quit()
            self._transcribe_thread.wait()
            self._transcribe_thread = None
            self._transcribe_worker = None

        self._subtitle_entries = entries
        self._current_subtitle_index = -1
        self.transcribe_progress.setVisible(False)
        self.status_label.setText(f"转写完成，共 {len(entries)} 条字幕")

        # 转写完成后用最终条目替换实时片段
        self._populate_subtitle_list()

        # 启用导出按钮
        self.export_srt_btn.setEnabled(True)
        self.export_txt_btn.setEnabled(True)

        # 自动保存 SRT + TXT 到视频同目录
        if entries and self._current_video_path:
            base_path = os.path.splitext(self._current_video_path)[0]
            saved = []
            try:
                srt_path = base_path + ".srt"
                TranscriberWorker.export_srt(entries, srt_path)
                saved.append("SRT")
            except Exception as exc:
                logger.warning("自动保存 SRT 失败: %s", exc)
            try:
                txt_path = base_path + ".txt"
                TranscriberWorker.export_txt(entries, txt_path)
                saved.append("TXT")
            except Exception as exc:
                logger.warning("自动保存 TXT 失败: %s", exc)
            if saved:
                self.status_label.setText(
                    f"转写完成，共 {len(entries)} 条字幕 | 已自动保存 {'/'.join(saved)}"
                )

        # 字幕只在播放中显示，下载/转写完成后暂不显示（等用户点播放）
        self.current_subtitle_label.setVisible(False)

    @Slot(str)
    def _on_transcribe_error(self, error: str) -> None:
        """转写出错"""
        if self._transcribe_thread:
            self._transcribe_thread.quit()
            self._transcribe_thread.wait()
            self._transcribe_thread = None
            self._transcribe_worker = None

        self.transcribe_progress.setVisible(False)
        self.status_label.setText("转写失败")
        QMessageBox.warning(self, "转写失败", error)

    # ── 视频播放 ───────────────────────────────────────────────────────────
    def _show_loading(self) -> None:
        """显示加载提示动画"""
        self.loading_label.setVisible(True)
        self._loading_dots = 0
        self._loading_timer.start(400)  # 每 400ms 更新一次

    def _hide_loading(self) -> None:
        """隐藏加载提示"""
        self._loading_timer.stop()
        self.loading_label.setVisible(False)

    def _update_loading_text(self) -> None:
        """更新加载提示的动态点点"""
        self._loading_dots = (self._loading_dots + 1) % 4
        dots = "." * self._loading_dots
        self.loading_label.setText(f"⏳ 加载中{dots}")

    def resizeEvent(self, event) -> None:
        """窗口大小变化时，重新定位叠加在视频上的元素"""
        super().resizeEvent(event)
        
        # 强制整个窗口布局立即更新
        if self.layout():
            self.layout().update()
        
        # 加载提示居中
        if self._video_stack:
            pw = self._video_stack.width()
            ph = self._video_stack.height()
            
            if self.loading_label.isVisible():
                lw, lh = 160, 40
                self.loading_label.move(
                    max(0, (pw - lw) // 2),
                    max(0, (ph - lh) // 2)
                )

        # 延迟更新字幕标签位置，确保布局计算完成
        QTimer.singleShot(10, self._position_subtitle_label)


    # ═══════════════════════════════════════════════════════════
    # VLC 轮询 & 辅助方法
    # ═══════════════════════════════════════════════════════════
    def _poll_vlc_state(self) -> None:
        """轮询 VLC 播放器状态/进度"""
        cur_state = self._vlc_player.get_state()
        if cur_state != self._vlc_prev_state:
            self._on_vlc_state_changed(cur_state)
            self._vlc_prev_state = cur_state
        cur_media = self._vlc_player.get_media()
        if cur_media is not self._vlc_prev_media:
            if cur_media is not None:
                self._on_duration_changed(self._vlc_player.get_length())
                self._hide_loading()
                display_title = self._get_display_title()
                self.status_label.setText(f"已加载: {display_title}")
                if self._auto_play_pending:
                    self._auto_play_pending = False
                    self._toggle_playback()
            self._vlc_prev_media = cur_media
        if cur_state == vlc.State.Playing:
            self._on_position_changed(self._vlc_player.get_time())

    def _get_display_title(self) -> str:
        """获取显示标题"""
        if hasattr(self, "_download_title") and self._download_title:
            return self._download_title
        if self._current_video_path:
            name = os.path.splitext(os.path.basename(self._current_video_path))[0]
            if name.lower() not in ("stream", "视频"):
                return name
        return "视频"

    def _on_slider_click(self, event, slider):
        """进度条任意位置点击时精准跳转"""
        if slider.maximum() == 0:
            return
        val = slider.minimum() + (slider.maximum() - slider.minimum()) * event.position().x() / slider.width()
        slider.setValue(int(val))
        self._seek_position(int(val))

    def _adjust_volume_up(self) -> None:
        if hasattr(self, "_vlc_player") and self._vlc_player:
            vol = min(100, self._vlc_player.audio_get_volume() + 10)
            self._vlc_player.audio_set_volume(vol)
            self.volume_slider.setValue(vol)

    def _adjust_volume_down(self) -> None:
        if hasattr(self, "_vlc_player") and self._vlc_player:
            vol = max(0, self._vlc_player.audio_get_volume() - 10)
            self._vlc_player.audio_set_volume(vol)
            self.volume_slider.setValue(vol)

    def _on_volume_slider_changed(self, value: int) -> None:
        if hasattr(self, "_vlc_player") and self._vlc_player:
            self._vlc_player.audio_set_volume(value)

    def _toggle_subtitle_display(self) -> None:
        """字幕文本区显示/隐藏开关"""
        self._subtitle_panel_visible = not self._subtitle_panel_visible
        self.subtitle_panel.setVisible(self._subtitle_panel_visible)
        if self._subtitle_panel_visible:
            self.subtitle_toggle_btn.setText("关字幕")
            self.subtitle_toggle_btn.setStyleSheet(
                "QPushButton { background-color: #EF5350; border: none; border-radius: 6px; "
                "color: white; font-size: 12px; font-weight: bold; } "
                "QPushButton:hover { background-color: #E53935; }"
            )
        else:
            self.subtitle_toggle_btn.setText("开字幕")
            self.subtitle_toggle_btn.setStyleSheet(
                "QPushButton { background-color: #66BB6A; border: none; border-radius: 6px; "
                "color: white; font-size: 12px; font-weight: bold; } "
                "QPushButton:hover { background-color: #43A047; }"
            )

    def _load_video(self, file_path: str, delay_set_source: bool = False) -> None:
        """加载视频文件"""

        # 确保绝对路径
        file_path = os.path.abspath(file_path)
        logger.info("加载视频: %s  存在=%s", file_path, os.path.exists(file_path))

        if not os.path.exists(file_path):
            QMessageBox.warning(self, "文件不存在", file_path)
            return

        # 确保当前视频路径正确
        self._current_video_path = file_path

        # 重置字幕状态
        self._subtitle_entries = []
        self._current_subtitle_index = -1
        self.subtitle_display.clear()
        self.current_subtitle_label.setVisible(False)
        self.current_subtitle_label.setText("")

        # 如果需要延迟设置媒体源（异步加载场景）
        if delay_set_source:
            self._pending_video_path = file_path
            return

        # 显示加载提示
        self._show_loading()
        self.status_label.setText("正在加载视频…")

        # 设置媒体源（用 file:/// URI）
        media_source = QUrl.fromLocalFile(file_path)
        logger.info("媒体源 URI: %s", media_source.toString())
        self._vlc_player.set_media(media)

        # 启用播放控制
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.position_slider.setEnabled(True)

        title = os.path.splitext(os.path.basename(file_path))[0]

        # 检查同名 SRT 字幕文件是否存在
        srt_path = os.path.splitext(file_path)[0] + ".srt"
        if os.path.isfile(srt_path):
            self._subtitle_entries = TranscriberWorker.parse_srt(srt_path)
            self.status_label.setText(
                f"已加载: {title}（{len(self._subtitle_entries)} 条字幕）"
            )
            self.export_srt_btn.setEnabled(True)
            self.export_txt_btn.setEnabled(True)
            if self._subtitle_entries:
                # 填充全文到字幕列表，播放时高亮同步
                self._populate_subtitle_list()
            logger.info("加载已有字幕: %s (%d 条)", srt_path, len(self._subtitle_entries))
        elif self._subtitle_entries:
            pass
        else:
            # 无字幕，启动转写
            self._start_transcribe(file_path)

    @Slot()
    def _toggle_playback(self) -> None:
        """切换播放/暂停"""
        from PySide6.QtWidgets import QApplication

        state = self._vlc_player.get_state()
        if state == vlc.State.Playing:
            self._vlc_player.pause()
            self.play_btn.setText("▶ 播放")
        else:
            # 确保当前视频在历史列表中
            if self._current_video_path:
                try:
                    self._add_to_history(
                        title=getattr(self, "_download_title", "") or os.path.splitext(os.path.basename(self._current_video_path))[0],
                        file_path=self._current_video_path,
                        duration=getattr(self, "_download_duration", 0),
                    )
                except Exception:
                    pass

            # 如果视频未加载，先异步加载
            if self._current_video_path and not self._vlc_player.get_media() is not None:
                self.status_label.setText("正在加载视频…")
                self._show_loading()
                # 强制刷新 UI，确保加载提示显示
                QApplication.processEvents()
                # 延迟加载，让 UI 有时间响应
                QTimer.singleShot(100, lambda: self._load_and_play())
                return

            # 播放前暂停转写，避免 CPU 争抢导致 UI 卡顿
            if self._transcribe_thread and self._transcribe_thread.isRunning():
                logger.info("播放前暂停转写线程")
                self._transcribe_worker.pause()
            try:
                self._vlc_player.play()
            except Exception as exc:
                logger.exception("播放异常: %s", exc)
                QMessageBox.warning(self, "播放异常", str(exc))
                return
            self.play_btn.setText("⏸ 暂停")

    def _load_and_play(self) -> None:
        """异步加载视频并自动播放"""
        from PySide6.QtWidgets import QApplication

        if not self._current_video_path:
            return

        # 先重置状态（不设置媒体源）
        self._load_video(self._current_video_path, delay_set_source=True)

        # 延迟设置媒体源，让 UI 有时间显示加载提示
        QTimer.singleShot(100, self._set_media_source)

    def _set_media_source(self) -> None:
        """设置媒体源（异步加载第二步）"""
        from PySide6.QtWidgets import QApplication

        if not self._pending_video_path:
            return

        # 再次确保加载提示可见
        self._show_loading()
        self.status_label.setText("正在初始化播放器…")
        QApplication.processEvents()

        # 设置媒体源
        file_path = self._pending_video_path
        self._pending_video_path = None

        # 确保 _current_video_path 指向当前文件（用于历史列表高亮）
        self._current_video_path = file_path

        media_source = QUrl.fromLocalFile(file_path)
        logger.info("设置媒体源: %s", media_source.toString())
        self._vlc_player.set_media(media)

        # 启用播放控制
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.position_slider.setEnabled(True)

        # 检查同名 SRT 字幕文件是否存在
        title = os.path.splitext(os.path.basename(file_path))[0]
        srt_path = os.path.splitext(file_path)[0] + ".srt"
        if os.path.isfile(srt_path):
            self._subtitle_entries = TranscriberWorker.parse_srt(srt_path)
            self.status_label.setText(
                f"已加载: {title}（{len(self._subtitle_entries)} 条字幕）"
            )
            self.export_srt_btn.setEnabled(True)
            self.export_txt_btn.setEnabled(True)
            if self._subtitle_entries:
                # 填充全文，播放时高亮同步
                self._populate_subtitle_list()
            logger.info("加载已有字幕: %s (%d 条)", srt_path, len(self._subtitle_entries))
        else:
            # 无字幕，启动转写
            self._start_transcribe(file_path)

        # 标记待播放
        self._auto_play_pending = True

    @Slot()
    def _stop_playback(self) -> None:
        """停止播放"""
        self._vlc_player.stop()
        self.play_btn.setText("▶ 播放")
        # 隐藏当前字幕
        self.current_subtitle_label.setVisible(False)
        # 停止后恢复转写
        if self._transcribe_thread and self._transcribe_thread.isRunning():
            logger.info("停止后恢复转写线程")
            self._transcribe_worker.resume()

    @Slot(int)
    def _seek_position(self, position: int) -> None:
        """跳转播放位置"""
        self._vlc_player.set_time(position)

    @Slot(int)
    def _on_position_changed(self, position_ms: int) -> None:
        """播放位置变化 → 更新字幕"""

        # 更新滑块
        if not self.position_slider.isSliderDown():
            self.position_slider.setValue(position_ms)

        # 更新时间标签
        duration = self._vlc_player.get_length()
        self.time_label.setText(
            f"{self._format_time(position_ms)} / {self._format_time(duration)}"
        )

        # 同步字幕（只在播放且有字幕时显示）
        if self._subtitle_entries:
            idx = TranscriberWorker.get_current_entry_index(
                self._subtitle_entries, position_ms
            )
            if idx >= 0:
                entry = self._subtitle_entries[idx]
                # 字幕内容有变化时再更新，避免频繁 setText
                if self.current_subtitle_label.text() != entry.text:
                    self.current_subtitle_label.setText(entry.text)
                # 播放中有字幕才让 label 可见（绝对定位，不碰布局）
                if not self.current_subtitle_label.isVisible():
                    self.current_subtitle_label.setVisible(True)
                    # 确保尺寸计算正确，然后重新定位到底部
                    self.current_subtitle_label.adjustSize()
                    self._position_subtitle_label()
                # 高亮下方字幕列表中对应的行
                self._highlight_subtitle_row(idx)
            else:
                self.current_subtitle_label.setVisible(False)
                self._highlight_subtitle_row(-1)
        else:
            self.current_subtitle_label.setVisible(False)
            self._highlight_subtitle_row(-1)

    @Slot(int)
    def _on_duration_changed(self, duration: int) -> None:
        """视频时长变化"""
        self.position_slider.setRange(0, duration)

    def _on_vlc_state_changed(self, new_state: vlc.State) -> None:
        if new_state == vlc.State.Playing:
            self.play_btn.setText("⏸ 暂停")
        elif new_state == vlc.State.Paused:
            self.play_btn.setText("▶ 播放")
        elif new_state in (vlc.State.Stopped, vlc.State.Ended):
            self.play_btn.setText("▶ 播放")
            self.current_subtitle_label.setVisible(False)
            self._highlight_subtitle_row(-1)
        self._refresh_history_list()

    def _on_media_status_changed(self, status) -> None:
        pass

    def _on_player_error(self, msg: str = "") -> None:
        logger.error("播放器错误: %s", msg)

    # ── 导出功能 ───────────────────────────────────────────────────────────
    @Slot()
    def _export_srt(self) -> None:
        """导出 SRT 字幕"""
        if not self._subtitle_entries:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存 SRT 文件", "", "SRT 字幕 (*.srt)"
        )
        if file_path:
            TranscriberWorker.export_srt(self._subtitle_entries, file_path)
            self.status_label.setText(f"已导出: {os.path.basename(file_path)}")

    @Slot()
    def _export_txt(self) -> None:
        """导出纯文本"""
        if not self._subtitle_entries:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存 TXT 文件", "", "文本文件 (*.txt)"
        )
        if file_path:
            TranscriberWorker.export_txt(self._subtitle_entries, file_path)
            self.status_label.setText(f"已导出: {os.path.basename(file_path)}")

    # ── 辅助方法 ───────────────────────────────────────────────────────────
    def _get_download_dir(self) -> str:
        """获取下载目录"""
        base_dir = Path(__file__).parent.parent / "downloads"
        base_dir.mkdir(exist_ok=True)
        return str(base_dir)

    def _get_ffmpeg_path(self) -> Optional[str]:
        """获取 FFmpeg 路径（None → 使用系统 PATH）"""
        # 如果 FFmpeg 在系统 PATH 中，返回 None
        # 如果打包到独立目录，返回相对路径
        return None

    @staticmethod
    def _format_time(ms: int) -> str:
        """毫秒 → MM:SS 格式"""
        seconds = ms // 1000
        minutes, seconds = divmod(seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"

    # ── 历史记录 ───────────────────────────────────────────────────────────
    def _get_history_path(self) -> str:
        """获取历史记录文件路径"""
        return str(Path(__file__).parent.parent / "history.json")

    def _load_history(self) -> None:
        """启动时加载历史记录，并扫描 downloads 目录发现本地文件"""

        # 1) 加载持久化的历史记录
        path = self._get_history_path()
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._video_history = json.load(f)
                logger.info("加载历史记录: %d 条", len(self._video_history))
            except Exception:
                self._video_history = []

        # 2) 扫描 downloads 目录，将本地已有视频/音频合并进历史列表
        self._scan_download_dir()

        self._refresh_history_list()

    def _scan_download_dir(self) -> None:
        """扫描下载目录，将已有视频/音频文件合并到历史记录（去重）"""
        download_dir = self._get_download_dir()
        if not os.path.isdir(download_dir):
            return

        # 已在历史记录中的文件路径集合（用于去重）
        existing_paths = {
            os.path.abspath(h.get("path", ""))
            for h in self._video_history
            if h.get("path")
        }

        # 已在历史记录中的文件名（不含扩展名）集合，用于同名视频/音频去重
        existing_stems = {
            os.path.splitext(os.path.basename(h.get("path", "")))[0]
            for h in self._video_history
            if h.get("path")
        }

        # 视频和音频扩展名
        video_extensions = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv"}
        audio_extensions = {".m4a", ".mp3", ".opus", ".flac", ".wav", ".aac"}
        media_extensions = video_extensions | audio_extensions

        # 收集本地文件，同名只保留视频版本
        # key: stem（文件名不含扩展名），value: 文件信息
        local_files: dict[str, dict] = {}

        try:
            for f in Path(download_dir).iterdir():
                if not f.is_file():
                    continue
                if f.suffix.lower() not in media_extensions:
                    continue

                abs_path = str(f.resolve())
                stem = f.stem

                # 路径已在历史记录中，跳过
                if abs_path in existing_paths:
                    continue

                # 同名文件去重：视频优先于音频
                if stem in local_files:
                    existing = local_files[stem]
                    existing_is_video = Path(existing["path"]).suffix.lower() in video_extensions
                    current_is_video = f.suffix.lower() in video_extensions
                    # 已有视频版本，跳过音频
                    if existing_is_video and not current_is_video:
                        continue
                    # 已有音频，当前是视频，替换
                    if not existing_is_video and current_is_video:
                        pass  # 下面会覆盖
                    # 同类型，保留较新的
                    elif f.stat().st_mtime <= os.path.getmtime(existing["path"]):
                        continue

                local_files[stem] = {
                    "title": stem,
                    "path": abs_path,
                    "duration": None,
                    "time": time.strftime(
                        "%Y-%m-%d %H:%M",
                        time.localtime(f.stat().st_mtime),
                    ),
                    "source": "local",
                }
        except Exception as exc:
            logger.warning("扫描下载目录失败: %s", exc)
            return

        new_entries = list(local_files.values())
        if new_entries:
            # 按修改时间排序，最新的在前
            new_entries.sort(
                key=lambda e: os.path.getmtime(e["path"]),
                reverse=True,
            )
            # 合并到历史记录前面
            self._video_history = new_entries + self._video_history
            logger.info("扫描发现 %d 个本地文件，已合并到历史记录", len(new_entries))
            self._save_history()

    def _save_history(self) -> None:
        """保存历史记录到文件"""
        try:
            with open(self._get_history_path(), "w", encoding="utf-8") as f:
                json.dump(self._video_history, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning("保存历史记录失败: %s", exc)

    def _add_to_history(self, title: str, file_path: str, duration: Optional[int] = None) -> None:
        """添加视频到历史记录（去重，最新的放最前面）"""
        file_path = os.path.abspath(file_path)

        # 去重：如果已存在则移到最前面，并更新元信息
        existing_entry = None
        remaining = []
        for h in self._video_history:
            if h.get("path") == file_path:
                existing_entry = h
            else:
                remaining.append(h)

        # 构造记录（保留已有信息，用新信息覆盖）
        entry = existing_entry or {}
        entry.update({
            "title": title or entry.get("title", os.path.basename(file_path)),
            "path": file_path,
            "duration": duration if duration is not None else entry.get("duration"),
            "time": time.strftime("%Y-%m-%d %H:%M"),
        })
        # 移除 local 标记，表示已被正式播放/下载过
        entry.pop("source", None)

        self._video_history = [entry] + remaining

        # 最多保留 100 条
        self._video_history = self._video_history[:100]

        self._refresh_history_list()
        self._save_history()

    def _refresh_history_list(self) -> None:
        """刷新历史列表 UI"""
        current_path = os.path.abspath(self._current_video_path) if self._current_video_path else ""
        self.history_list.clear()

        for item in self._video_history:
            path = item.get("path", "")
            title = item.get("title", os.path.basename(path))
            dur = item.get("duration")
            add_time = item.get("time", "")
            source = item.get("source", "")

            # 格式化显示文本
            if dur and dur > 0:
                dur_str = f" [{self._format_time(int(dur * 1000))}]"
            else:
                dur_str = ""

            # 高亮当前正在播放的视频
            is_current = (os.path.abspath(path) == current_path)
            prefix = "▶ " if is_current else "  "

            display_text = f"{prefix}{title}{dur_str}"
            if add_time:
                display_text += f"  ({add_time})"

            list_item = QListWidgetItem(display_text)
            list_item.setData(Qt.ItemDataRole.UserRole, path)

            if is_current:
                list_item.setForeground(QColor("#0078D4"))
                font = list_item.font()
                font.setBold(True)
                list_item.setFont(font)

            # 如果文件不存在，灰色显示
            if not os.path.isfile(path):
                list_item.setForeground(QColor("#484F58"))

            self.history_list.addItem(list_item)

    @Slot(object)
    def _on_history_item_double_clicked(self, item) -> None:
        """双击历史列表项 → 切换视频"""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path or not os.path.isfile(file_path):
            QMessageBox.warning(self, "文件不存在", f"文件已被删除或移动:\n{file_path}")
            return

        # 停止当前播放
        if self._vlc_player.get_state() == vlc.State.Playing:
            self._vlc_player.stop()
        self.play_btn.setText("▶ 播放")

        # 取消正在进行的转写
        if self._transcribe_thread and self._transcribe_thread.isRunning():
            self._transcribe_worker.cancel()
            self._transcribe_thread.quit()
            self._transcribe_thread.wait(3000)
            self._transcribe_thread = None
            self._transcribe_worker = None

        # 切换视频
        self._current_video_path = file_path
        self._refresh_history_list()
        self.status_label.setText("正在加载视频…")
        self._show_loading()

        from PySide6.QtWidgets import QApplication as _App
        _App.processEvents()

        QTimer.singleShot(100, lambda: self._load_and_play())

    @Slot()
    def _on_history_clear(self) -> None:
        """清空历史记录"""
        reply = QMessageBox.question(
            self, "确认清空", "确定要清空所有历史记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._video_history.clear()
            self._refresh_history_list()
            self._save_history()

    # ── 字幕标签布局管理 ─────────────────────────────────────────────────
    def _position_subtitle_label(self) -> None:
        """将字幕标签定位到视频区域底部居中（绝对定位，不影响布局）"""
        if not self._video_stack:
            return
        # 确保尺寸是最新的
        self.current_subtitle_label.adjustSize()
        pw = self._video_stack.width()
        ph = self._video_stack.height()
        sl_w = self.current_subtitle_label.width()
        sl_h = self.current_subtitle_label.height()
        # 底部边距 12px
        self.current_subtitle_label.move(
            max(0, (pw - sl_w) // 2),
            max(0, ph - sl_h - 12)
        )

    # ── 字幕列表同步高亮 ──────────────────────────────────────────────────
    def _populate_subtitle_list(self) -> None:
        """将 _subtitle_entries 填充到 subtitle_display (QListWidget)"""
        self.subtitle_display.clear()
        self._current_subtitle_index = -1
        for entry in self._subtitle_entries:
            item = QListWidgetItem(entry.text)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.subtitle_display.addItem(item)

    def _highlight_subtitle_row(self, index: int) -> None:
        """
        高亮指定行，取消之前的高亮，并自动滚动确保可见。
        index == -1 时取消所有高亮。
        只在 index 变化时才执行，避免频繁重绘。
        """
        if index == self._current_subtitle_index:
            return
        # 取消旧高亮
        old = self._current_subtitle_index
        if 0 <= old < self.subtitle_display.count():
            old_item = self.subtitle_display.item(old)
            old_item.setForeground(QColor("#6E7681"))
            old_item.setBackground(QColor("transparent"))
            old_item.setFont(QFont("Microsoft YaHei", 13))
        # 设置新高亮
        self._current_subtitle_index = index
        if 0 <= index < self.subtitle_display.count():
            new_item = self.subtitle_display.item(index)
            new_item.setForeground(QColor("#FFFFFF"))
            new_item.setBackground(QColor("#0078D4"))
            new_item.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Bold))
            self.subtitle_display.scrollToItem(
                new_item,
                QAbstractItemView.ScrollHint.PositionAtCenter,
            )

    # ── 窗口关闭清理 ──────────────────────────────────────────────────────
    def closeEvent(self, event) -> None:
        """窗口关闭时清理资源"""

        # 停止播放器
        self._vlc_player.stop()

        # 停止后台线程
        if self._download_thread and self._download_thread.isRunning():
            self._download_worker.cancel()
            self._download_thread.quit()
            self._download_thread.wait(3000)

        if self._transcribe_thread and self._transcribe_thread.isRunning():
            self._transcribe_worker.cancel()
            self._transcribe_thread.quit()
            self._transcribe_thread.wait(3000)

        event.accept()

# ─────────────────────────────────────────────────────────────────────────
# 程序入口（调试用）
# ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
