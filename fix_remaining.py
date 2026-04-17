#!/usr/bin/env python3
"""最终补丁：修复剩余未匹配项"""
import ast

PATH = 'gui/main_window.py'

def load(): return open(PATH, encoding='utf-8').read()
def save(c): open(PATH, 'w', encoding='utf-8').write(c)

def do(old, new, tag=''):
    c = load()
    if old not in c:
        print(f'  SKIP [{tag}]: not found')
        return
    c = c.replace(old, new, 1)
    ast.parse(c)
    save(c)
    print(f'  OK [{tag}]')

# 1. _setup_media_player 完全重写
do('''    # ── 媒体播放器初始化 ───────────────────────────────────────────────────
    def _setup_media_player(self) -> None:
        """初始化 QMediaPlayer 和音频输出"""

        # 注：禁用硬件解码的环境变量 QT_MULTIMEDIA_PREFER_SOFTWARE=1
        # 已在 main.py 的 QApplication 创建前设置，此处无需重复。

        # 音频输出（Qt 6.2+ 必需）
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0.8)

        # 媒体播放器
        self.media_player = QMediaPlayer()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)

        # 错误处理
        self.media_player.errorOccurred.connect(self._on_player_error)''',
'''    # ── 媒体播放器初始化 ───────────────────────────────────────────────────
    def _setup_media_player(self) -> None:
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
        if sys.platform == "win32":
            self._vlc_player.set_hwnd(self.video_widget.winId())
        elif sys.platform == "darwin":
            self._vlc_player.set_nsobject(int(self.video_widget.winId()))
        self._vlc_player.audio_set_volume(80)
        # 轮询定时器：VLC 无 Qt 信号
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(80)
        self._poll_timer.timeout.connect(self._poll_vlc_state)
        self._poll_timer.start()
        self._vlc_prev_state = None
        self._vlc_prev_media = None

        # VLC 状态通过 _poll_timer 轮询，不需要 Qt 信号

        # 错误处理
        self._on_player_error = lambda msg: logger.error("播放错误: %s", msg)''', 'setup')

# 2. 移除 media_player 信号连接（在 _connect_signals 中）
do('''        # 播放器状态变化
        self.media_player.positionChanged.connect(self._on_position_changed)
        self.media_player.durationChanged.connect(self._on_duration_changed)
        self.media_player.playbackStateChanged.connect(self._on_state_changed)
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)''',
'''        # VLC 状态通过 _poll_timer 轮询，不需要 Qt 信号''', 'signals')

# 3. _load_video: setSource 两处
do('        self.media_player.setSource(media_source)',
  '        media = self._vlc_instance.media_new(media_source)\n        self._vlc_player.set_media(media)', 'setSource')

# 4. _stop_playback 清理
do('''    @Slot()
    def _stop_playback(self) -> None:
        """停止播放"""
        self._vlc_player.stop()
        self.play_btn.setText("▶ 播放")
        # 隐藏当前字幕
        self.current_subtitle_label.setVisible(False)
        # 停止后恢复转写
        if self._transcribe_thread and self._transcribe_thread.isRunning():
            logger.info("停止后恢复转写线程")
            self._transcribe_worker.resume()''',
'''    def _stop_playback(self) -> None:
        """停止播放"""
        self._vlc_player.stop()
        self.play_btn.setText("▶ 播放")
        self.position_slider.setValue(0)
        self._sync_last_pos_ms = -1
        self.volume_slider.setEnabled(False)
        self.volume_up_btn.setEnabled(False)
        self.volume_down_btn.setEnabled(False)
        self.subtitle_toggle_btn.setEnabled(False)''', 'stop')

# 5. _add_to_history 不置顶
do('''    def _add_to_history(self, title: str, file_path: str, duration: Optional[int] = None) -> None:
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
        # 安全保护：禁止 "stream" 作为标题（流媒体临时文件名泄漏）
        safe_fallback = os.path.splitext(os.path.basename(file_path))[0]
        if safe_fallback.lower() in ("stream", "视频"):
            safe_fallback = existing_entry.get("title", "视频") if existing_entry else "视频"
        entry.update({
            "title": title or entry.get("title", safe_fallback),
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
        self._save_history()''',
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

# 6. _toggle_subtitle_display
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

# 7. subtitle_toggle_btn 初始禁用（修复之前 SKIP）
do('        self.subtitle_toggle_btn.clicked.connect(self._toggle_subtitle_display)',
  '        self.subtitle_toggle_btn.clicked.connect(self._toggle_subtitle_display)\n        self.subtitle_toggle_btn.setEnabled(False)\n        self._subtitle_panel_visible = True', 'toggle-init')

# 8. _on_media_status_changed 简化
do('''    @Slot("QMediaPlayer::MediaStatus")
    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        """媒体状态变化（加载完成时启动转写）"""
        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            if not self._transcribe_thread or not self._transcribe_thread.isRunning():
                if self._subtitle_entries:
                    logger.info("已有字幕，跳过转写")
                else:
                    self._start_transcribe(self._current_video_path)''',
'''    def _on_media_status_changed(self, status) -> None:
        """VLC 不需要，状态由 _poll_vlc_state 处理"""
        pass''', 'media-status')

# 9. _on_player_error 简化
do('''    @Slot(QMediaPlayer.Error, str)
    def _on_player_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        """播放错误"""
        if error != QMediaPlayer.Error.NoError:
            logger.error("播放错误: %s - %s", error, error_string)''',
'''    def _on_player_error(self, msg: str) -> None:
        logger.error("播放错误: %s", msg)''', 'error')

# Final verify
c = load()
try:
    ast.parse(c)
    save(c)
    print('\nFINAL: Syntax OK')
except SyntaxError as e:
    print(f'\nFINAL ERROR line {e.lineno}: {e.msg}')
