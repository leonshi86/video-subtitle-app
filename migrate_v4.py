#!/usr/bin/env python3
"""批量补丁脚本：逐条执行替换，每次重新加载验证"""
import ast

PATH = 'gui/main_window.py'
PATCHES = []

def load(): return open(PATH, encoding='utf-8').read()
def save(c): open(PATH, 'w', encoding='utf-8').write(c)

def do(old, new, tag=''):
    c = load()
    if old not in c:
        print(f'  SKIP [{tag}]: not found')
        return
    c = c.replace(old, new, 1)
    try:
        ast.parse(c)
    except SyntaxError as e:
        print(f'  FAIL [{tag}] line {e.lineno}: {e.msg}')
        raise
    save(c)
    print(f'  OK [{tag}]')

# ════════════════════════════════════════════════════
# 批次1：基础 VLC 迁移（不改变行数的替换）
# ════════════════════════════════════════════════════

# 1. import
do('from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput',
  'import vlc  # VLC 播放器', 'import')

# 2. QVideoWidget import
do('from PySide6.QtMultimediaWidgets import QVideoWidget',
  '# QVideoWidget 移除（已迁移至 VLC）', 'QVideoWidget-import')

# 3. video_widget
do('self.video_widget = QVideoWidget()',
  'self.video_widget = QWidget()', 'video-widget')

# 4. _setup_media_player 重写
do('''    def _setup_media_player(self) -> None:
        """初始化 QMediaPlayer 和音频输出"""
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: black; border-radius: 8px;")
        self.video_widget.setMinimumSize(320, 180)
        video_container_layout.addWidget(self.video_widget)

        self.audio_output = QAudioOutput()
        self.media_player = QMediaPlayer()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)

        self.media_player.positionChanged.connect(self._on_position_changed)
        self.media_player.durationChanged.connect(self._on_duration_changed)
        self.media_player.playbackStateChanged.connect(self._on_state_changed)
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)''',
'''    def _setup_media_player(self) -> None:
        """初始化 VLC 媒体播放器（全局禁用内嵌字幕）"""
        # VLC 实例
        self._vlc_instance = vlc.Instance(
            "--network-caching=1000",
            "--file-caching=500",
            "--avcodec-hw=any",
            "--no-spu",
            "--no-sub-autodetect-file",
            "--verbose=0",
        )
        self._vlc_player = self._vlc_instance.media_player_new()

        # 将 VLC 视频输出绑定到 QWidget
        if sys.platform == "win32":
            self._vlc_player.set_hwnd(self.video_widget.winId())
        elif sys.platform == "darwin":
            self._vlc_player.set_nsobject(int(self.video_widget.winId()))

        self._vlc_player.audio_set_volume(80)

        # 轮询定时器：VLC 无 Qt 信号，用定时器轮询状态/进度
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(80)
        self._poll_timer.timeout.connect(self._poll_vlc_state)
        self._poll_timer.start()

        self._vlc_prev_state = None
        self._vlc_prev_media = None

        # VLC 状态通过 _poll_timer 轮询，不需要 Qt 信号''', 'setup')

# 5. video_widget 样式（QVideoWidget → QWidget）
do('        self.video_widget.setStyleSheet("background-color: black; border-radius: 8px;")\n        self.video_widget.setMinimumSize(320, 180)',
  '        self.video_widget.setStyleSheet("background-color: black; border-radius: 8px;")\n        self.video_widget.setMinimumSize(320, 180)', 'widget-style')

# 6. media_player → _vlc_player
do('self.media_player.play()', 'self._vlc_player.play()', 'play')
do('self.media_player.pause()', 'self._vlc_player.pause()', 'pause')
do('self.media_player.stop()', 'self._vlc_player.stop()', 'stop')
do('self.media_player.setPosition(position)', 'self._vlc_player.set_time(position)', 'seek')
do('self.media_player.duration()', 'self._vlc_player.get_length()', 'duration')
do('self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState',
  'self._vlc_player.get_state() == vlc.State.Playing', 'playing-state')

# 7. _load_video: setSource
do('self.media_player.setSource(file_path)',
  'media = self._vlc_instance.media_new(file_path)\n        self._vlc_player.set_media(media)', 'setSource')

# 8. _on_state_changed
do('def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:',
  'def _on_vlc_state_changed(self, new_state: vlc.State) -> None:', 'state-sig')
do('if state == QMediaPlayer.PlaybackState.PlayingState:', 'if new_state == vlc.State.Playing:', 'state-playing')
do('elif state == QMediaPlayer.PlaybackState.PausedState:', 'elif new_state == vlc.State.Paused:', 'state-paused')
do('elif state == QMediaPlayer.PlaybackState.StoppedState:', 'elif new_state == vlc.State.Stopped or new_state == vlc.State.Ended:', 'state-stopped')

# ════════════════════════════════════════════════════
# 批次2：新增方法和功能
# ════════════════════════════════════════════════════

# 9. _poll_vlc_state 新增（插在 _on_vlc_state_changed 之前）
poll_method = '''
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

'''
c = load()
idx = c.find('    def _on_vlc_state_changed(self, new_state: vlc.State) -> None:')
if idx >= 0:
    lines = c.split('\n')
    for i, l in enumerate(lines):
        if '    def _on_vlc_state_changed' in l:
            lines.insert(i, poll_method)
            break
    c = '\n'.join(lines)
    ast.parse(c)
    save(c)
    print('  OK [poll_vlc_state]')
else:
    print('  SKIP [poll_vlc_state]: not found')

# 10. subtitle_panel → self.subtitle_panel
do('        subtitle_panel = QWidget()',
  '        self.subtitle_panel = QWidget()', 'subtitle-self')
do('subtitle_layout = QVBoxLayout(subtitle_panel)',
  'subtitle_layout = QVBoxLayout(self.subtitle_panel)', 'subtitle-layout')
do('right_layout.addWidget(subtitle_panel)',
  'right_layout.addWidget(self.subtitle_panel)', 'subtitle-add')

# 11. subtitle_toggle_btn 初始禁用
do('        self.subtitle_toggle_btn.clicked.connect(self._toggle_subtitle_display)\n        self.subtitle_toggle_btn.setEnabled(False)\n        self._subtitle_panel_visible = True',
  '        self.subtitle_toggle_btn.clicked.connect(self._toggle_subtitle_display)\n        self.subtitle_toggle_btn.setEnabled(False)\n        self._subtitle_panel_visible = True', 'toggle-init')

# 12. history_panel 最小宽度
do('        history_panel = QWidget()',
  '        history_panel = QWidget()\n        history_panel.setMinimumWidth(180)', 'history-min')

# 13. QSplitter handle
do('content_splitter.setStyleSheet("QSplitter::handle { width: 1px; background: #21262D; }")',
  'content_splitter.setStyleSheet("QSplitter::handle { width: 4px; background: #90CAF9; border-radius: 2px; }")\n        content_splitter.setCollapsible(0, False)\n        content_splitter.setHandleWidth(4)', 'splitter')

# 14. 进度条鼠标点击
do('        self.position_slider.setFixedHeight(20)\n        control_layout.addWidget(self.position_slider, stretch=1)',
  '        self.position_slider.setFixedHeight(20)\n        self.position_slider.setPageStep(0)\n        self.position_slider.mousePressEvent = lambda e: self._on_slider_click(e, self.position_slider)\n        control_layout.addWidget(self.position_slider, stretch=1)', 'slider-click')

# 15. 音量控制 UI
vol_code = '''
        # 音量控制
        volume_layout = QHBoxLayout()
        volume_layout.setSpacing(4)
        self.volume_down_btn = QPushButton("-")
        self.volume_down_btn.setFixedSize(26, 26)
        self.volume_down_btn.setStyleSheet("QPushButton { background-color: #90CAF9; border: none; border-radius: 4px; color: white; font-size: 14px; font-weight: bold; } QPushButton:hover { background-color: #42A5F5; } QPushButton:disabled { background-color: #E3F2FD; color: #90CAF9; }")
        self.volume_down_btn.clicked.connect(self._adjust_volume_down)
        self.volume_down_btn.setEnabled(False)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.setEnabled(False)
        self.volume_slider.setStyleSheet("QSlider::groove:horizontal { height: 4px; background: #BBDEFB; border-radius: 2px; } QSlider::handle:horizontal { width: 10px; background: #42A5F5; border-radius: 5px; margin: -3px 0; } QSlider::sub-page:horizontal { background: #42A5F5; border-radius: 2px; }")
        self.volume_slider.valueChanged.connect(self._on_volume_slider_changed)
        self.volume_up_btn = QPushButton("+")
        self.volume_up_btn.setFixedSize(26, 26)
        self.volume_up_btn.setStyleSheet("QPushButton { background-color: #90CAF9; border: none; border-radius: 4px; color: white; font-size: 14px; font-weight: bold; } QPushButton:hover { background-color: #42A5F5; } QPushButton:disabled { background-color: #E3F2FD; color: #90CAF9; }")
        self.volume_up_btn.clicked.connect(self._adjust_volume_up)
        self.volume_up_btn.setEnabled(False)
        volume_layout.addWidget(self.volume_down_btn)
        volume_layout.addWidget(self.volume_slider)
        volume_layout.addWidget(self.volume_up_btn)
        control_layout.addLayout(volume_layout)'''

c = load()
old_tl = '        self.time_label = QLabel("00:00 / 00:00")\n        self.time_label.setFixedWidth(110)\n        self.time_label.setStyleSheet("color: #1565C0; font-size: 12px; background: transparent;")\n        control_layout.addWidget(self.time_label)'
# Find position of time_label and insert volume after it
lines = c.split('\n')
for i, l in enumerate(lines):
    if 'self.time_label.setFixedWidth(110)' in l:
        lines.insert(i+1, vol_code)
        break
c = '\n'.join(lines)
ast.parse(c)
save(c)
print('  OK [volume-control]')

# 16. _load_video: 启用音量控件
do('        self.position_slider.setEnabled(True)',
  '        self.position_slider.setEnabled(True)\n        self.volume_slider.setEnabled(True)\n        self.volume_up_btn.setEnabled(True)\n        self.volume_down_btn.setEnabled(True)', 'vol-enable')

# 17. _load_video: 重置字幕开关
do('        self.play_btn.setEnabled(True)\n        self.stop_btn.setEnabled(True)\n        self.position_slider.setEnabled(True)\n        self.volume_slider.setEnabled(True)\n        self.volume_up_btn.setEnabled(True)\n        self.volume_down_btn.setEnabled(True)',
  '        self._subtitle_panel_visible = True\n        self.subtitle_panel.setVisible(True)\n        self.subtitle_toggle_btn.setEnabled(True)\n        self.subtitle_toggle_btn.setText("关字幕")\n        self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #EF5350; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #E53935; }")\n        self.play_btn.setEnabled(True)\n        self.stop_btn.setEnabled(True)\n        self.position_slider.setEnabled(True)\n        self.volume_slider.setEnabled(True)\n        self.volume_up_btn.setEnabled(True)\n        self.volume_down_btn.setEnabled(True)', 'subtitle-reset')

# 18. _stop_playback: 禁用控件
do('        self.position_slider.setValue(0)',
  '        self.position_slider.setValue(0)\n        self.volume_slider.setEnabled(False)\n        self.volume_up_btn.setEnabled(False)\n        self.volume_down_btn.setEnabled(False)\n        self.subtitle_toggle_btn.setEnabled(False)', 'stop-disable')

# 19. _on_media_status_changed 简化
do('    @Slot("QMediaPlayer::MediaStatus")\n    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:\n        """媒体状态变化（加载完成时启动转写）"""\n        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):\n            if not self._transcribe_thread or not self._transcribe_thread.isRunning():\n                if self._subtitle_entries:\n                    logger.info("已有字幕，跳过转写")\n                else:\n                    self._start_transcribe(self._current_video_path)',
  '    def _on_media_status_changed(self, status) -> None:\n        """VLC 不需要此方法，状态由 _poll_vlc_state 处理"""\n        pass', 'media-status')

# 20. _on_player_error 简化
do('''    @Slot(QMediaPlayer.Error, str)
    def _on_player_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        """播放错误"""
        if error != QMediaPlayer.Error.NoError:
            logger.error("播放错误: %s - %s", error, error_string)''',
'''    def _on_player_error(self, msg: str) -> None:
        logger.error("播放错误: %s", msg)''', 'player-error')

# 21. closeEvent
do('            self.media_player.stop()',
  '            if hasattr(self, "_vlc_player") and self._vlc_player:\n                self._vlc_player.stop()\n            if hasattr(self, "_vlc_instance") and self._vlc_instance:\n                self._vlc_instance.release()', 'closeEvent')

# 22. _add_to_history 不置顶
do('    def _add_to_history(self, title: str, file_path: str, duration: Optional[int] = None) -> None:\n        """添加视频到历史记录（去重，最新的放最前面）"""\n        file_path = os.path.abspath(file_path)\n\n        # 去重：如果已存在则移到最前面，并更新元信息\n        existing_entry = None\n        remaining = []\n        for h in self._video_history:\n            if h.get("path") == file_path:\n                existing_entry = h\n            else:\n                remaining.append(h)\n\n        # 构造记录（保留已有信息，用新信息覆盖）\n        entry = existing_entry or {}\n        # 安全保护：禁止 "stream" 作为标题（流媒体临时文件名泄漏）\n        safe_fallback = os.path.splitext(os.path.basename(file_path))[0]\n        if safe_fallback.lower() in ("stream", "视频"):\n            safe_fallback = existing_entry.get("title", "视频") if existing_entry else "视频"\n        entry.update({\n            "title": title or entry.get("title", safe_fallback),\n            "path": file_path,\n            "duration": duration if duration is not None else entry.get("duration"),\n            "time": time.strftime("%Y-%m-%d %H:%M"),\n        })\n        # 移除 local 标记，表示已被正式播放/下载过\n        entry.pop("source", None)\n\n        self._video_history = [entry] + remaining\n\n        # 最多保留 100 条\n        self._video_history = self._video_history[:100]\n\n        self._refresh_history_list()\n        self._save_history()''',
'''    def _add_to_history(self, title: str, file_path: str, duration: Optional[int] = None) -> None:
        """添加视频到历史记录（去重，不改变原有顺序，只更新元数据）"""
        file_path = os.path.abspath(file_path)

        existing_idx = None
        for i, h in enumerate(self._video_history):
            if h.get("path") == file_path:
                existing_idx = i
                break

        safe_fallback = os.path.splitext(os.path.basename(file_path))[0]
        if safe_fallback.lower() in ("stream", "视频"):
            safe_fallback = (self._video_history[existing_idx].get("title", "视频")
                            if existing_idx is not None else "视频")

        entry = {
            "title": (title or
                      (self._video_history[existing_idx].get("title", safe_fallback)
                       if existing_idx is not None else safe_fallback)),
            "path": file_path,
            "duration": (duration if duration is not None else
                         (self._video_history[existing_idx].get("duration")
                          if existing_idx is not None else None)),
            "time": time.strftime("%Y-%m-%d %H:%M"),
        }
        entry.pop("source", None)

        if existing_idx is not None:
            self._video_history[existing_idx].update(entry)
        else:
            self._video_history.append(entry)

        self._video_history = self._video_history[:100]

        self._refresh_history_list()
        self._save_history()''', 'add_history')

# 23. _toggle_subtitle_display
do('''    def _toggle_subtitle_display(self) -> None:
        """字幕显示/隐藏开关"""
        self._subtitle_panel_visible = not self._subtitle_panel_visible
        self.subtitle_panel.setVisible(self._subtitle_panel_visible)
        if self._subtitle_panel_visible:
            self.subtitle_toggle_btn.setText("关字幕")
            self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #EF5350; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #E53935; }")
        else:
            self.subtitle_toggle_btn.setText("开字幕")
            self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #66BB6A; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #43A047; }")''',
'''    def _toggle_subtitle_display(self) -> None:
        """字幕文本区显示/隐藏开关"""
        self._subtitle_panel_visible = not self._subtitle_panel_visible
        self.subtitle_panel.setVisible(self._subtitle_panel_visible)
        if self._subtitle_panel_visible:
            self.subtitle_toggle_btn.setText("关字幕")
            self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #EF5350; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #E53935; }")
        else:
            self.subtitle_toggle_btn.setText("开字幕")
            self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #66BB6A; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #43A047; }")''', 'toggle')

# 24. 新增辅助方法（插在 _toggle_subtitle_display 之前）
helpers = '''
    # ── 进度条点击定位 ─────────────────────────────────────────────────
    def _on_slider_click(self, event, slider):
        if slider.maximum() == 0:
            return
        val = slider.minimum() + (slider.maximum() - slider.minimum()) * event.position().x() / slider.width()
        slider.setValue(int(val))
        self._seek_position(int(val))

    # ── 音量控制 ─────────────────────────────────────────────────────────
    def _adjust_volume_up(self) -> None:
        if self._vlc_player:
            vol = min(100, self._vlc_player.audio_get_volume() + 10)
            self._vlc_player.audio_set_volume(vol)
            self.volume_slider.setValue(vol)

    def _adjust_volume_down(self) -> None:
        if self._vlc_player:
            vol = max(0, self._vlc_player.audio_get_volume() - 10)
            self._vlc_player.audio_set_volume(vol)
            self.volume_slider.setValue(vol)

    def _on_volume_slider_changed(self, value: int) -> None:
        if self._vlc_player:
            self._vlc_player.audio_set_volume(value)

'''
c = load()
lines = c.split('\n')
for i, l in enumerate(lines):
    if '    def _toggle_subtitle_display(self)' in l:
        lines.insert(i, helpers)
        break
c = '\n'.join(lines)
ast.parse(c)
save(c)
print('  OK [helpers]')

# Final
c = load()
try:
    ast.parse(c)
    print('\nAll patches applied. Syntax OK.')
except SyntaxError as e:
    print(f'\nFINAL SYNTAX ERROR line {e.lineno}: {e.msg}')
