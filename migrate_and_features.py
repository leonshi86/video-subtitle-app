#!/usr/bin/env python3
"""完整重做：从 QMediaPlayer 迁移到 VLC + 添加所有新功能"""
import ast, re

PATH = 'gui/main_window.py'

def load():
    with open(PATH, encoding='utf-8') as f:
        return f.read()

def save(c):
    with open(PATH, 'w', encoding='utf-8') as f:
        f.write(c)

def check(c, tag):
    try:
        ast.parse(c)
        print(f'  [{tag}] OK')
    except SyntaxError as e:
        print(f'  [{tag}] SYNTAX ERROR line {e.lineno}: {e.msg}')
        raise

def ins(c, needle, code, tag=''):
    lines = c.split('\n')
    for i, l in enumerate(lines):
        if needle in l:
            lines.insert(i+1, code)
            print(f'  [{tag}] +{i+1}')
            return '\n'.join(lines)
    print(f'  [{tag}] WARN: not found: {needle!r}')
    return c

def rep(c, old, new, tag=''):
    if old not in c:
        print(f'  [{tag}] WARN: not found')
        return c
    c = c.replace(old, new, 1)
    print(f'  [{tag}] replaced')
    return c

def rep_first(c, old, new, tag=''):
    lines = c.split('\n')
    for i, l in enumerate(lines):
        if old in l:
            lines[i] = new
            print(f'  [{tag}] line {i+1}')
            return '\n'.join(lines)
    print(f'  [{tag}] WARN: not found')
    return c

# ── R1: 添加 vlc import，替换 QMediaPlayer import ──
c = rep(load(),
    'from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput',
    'import vlc  # VLC 播放器',
    'R1')

# ── R2: 替换 _setup_media_player ──
old_setup = '''    def _setup_media_player(self) -> None:
        """初始化媒体播放器"""
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: black; border-radius: 8px;")
        self.video_widget.setMinimumSize(320, 180)
        video_container_layout.addWidget(self.video_widget)

        self.audio_output = QAudioOutput()
        self.media_player = QMediaPlayer()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)

        self.media_player.positionChanged.connect(self._on_media_position_changed)
        self.media_player.durationChanged.connect(self._on_media_duration_changed)
        self.media_player.playbackStateChanged.connect(self._on_media_playback_state_changed)
        self.media_player.errorOccurred.connect(self._on_media_error)'''

new_setup = '''    def _setup_media_player(self) -> None:
        """初始化 VLC 媒体播放器"""
        self.video_widget = QWidget()
        self.video_widget.setStyleSheet("background-color: black; border-radius: 8px;")
        self.video_widget.setMinimumSize(320, 180)
        video_container_layout.addWidget(self.video_widget)

        # VLC 实例（全局禁用内嵌字幕）
        self._vlc_instance = vlc.Instance(
            "--network-caching=1000",
            "--file-caching=500",
            "--avcodec-hw=any",
            "--no-spu",
            "--no-sub-autodetect-file",
            "--verbose=0",
        )
        self._vlc_player = self._vlc_instance.media_player_new()

        # 将 VLC 视频输出绑定到 QWidget（通过 Win32 HWND）
        if sys.platform == "win32":
            self._vlc_player.set_hwnd(self.video_widget.winId())
        elif sys.platform == "darwin":
            self._vlc_player.set_nsobject(int(self.video_widget.winId()))

        # 音量默认 80%
        self._vlc_player.audio_set_volume(80)

        # 轮询定时器：VLC 没有 Qt 信号，用定时器轮询状态/进度
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(80)
        self._poll_timer.timeout.connect(self._poll_vlc_state)
        self._poll_timer.start()

        # 用于检测状态跳变的缓存变量
        self._vlc_prev_state = None
        self._vlc_prev_media = None'''

c = rep(c, old_setup, new_setup, 'R2')

# ── R3: 替换 positionChanged signal 连接（移除 QMediaPlayer 信号）─
c = rep(c,
    '        self.media_player.positionChanged.connect(self._on_media_position_changed)\n        self.media_player.durationChanged.connect(self._on_media_duration_changed)\n        self.media_player.playbackStateChanged.connect(self._on_media_playback_state_changed)\n        self.media_player.errorOccurred.connect(self._on_media_error)',
    '        # VLC 状态通过 _poll_timer 轮询，不需要 Qt 信号',
    'R3')

# ── R4: _on_media_position_changed → 重命名为 _on_position_changed，改为内部方法 ──
# 找旧方法并替换
old_pos = '''    def _on_media_position_changed(self, position_ms: int) -> None:
        """播放位置变化 → 更新字幕"""
        # 滑块 + 时间标签：始终实时
        if not self.position_slider.isSliderDown():
            self.position_slider.setValue(position_ms)
        duration = self.media_player.duration()
        self.time_label.setText(
            f"{self._format_time(position_ms)} / {self._format_time(duration)}"
        )

        # ── 字幕同步：节流 ≥ 80ms ──
        last = self._sync_last_pos_ms
        delta = position_ms - last if last >= 0 else 999999
        is_seek = (delta < 0) or (delta > 500)
        if not is_seek and delta < 80:
            return
        self._sync_last_pos_ms = position_ms

        if self._subtitle_entries:
            idx = TranscriberWorker.get_current_entry_index(
                self._subtitle_entries, position_ms
            )
            if idx >= 0:
                self._highlight_subtitle_row(idx)
            else:
                self._highlight_subtitle_row(-1)
        else:
            self._highlight_subtitle_row(-1)

    def _on_media_duration_changed(self, duration: int) -> None:
        """视频时长变化"""
        if duration <= 0:
            return
        if self.position_slider.maximum() != duration:
            self.position_slider.setRange(0, duration)
        # 如果有 .txt 加载的无时间轴条目，均匀分配时间轴
        if self._subtitle_entries:
            needs_rebuild = any(e.start_sec == 0.0 and e.end_sec == 0.0 for e in self._subtitle_entries)
            if needs_rebuild:
                self._distribute_time_axis(duration / 1000.0)
                self._populate_subtitle_list()

    def _on_media_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        """播放状态变化"""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText("⏸ 暂停")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.play_btn.setText("▶ 播放")
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            self.play_btn.setText("▶ 播放")
            self.current_subtitle_label.setVisible(False)
            self._highlight_subtitle_row(-1)
        elif state == QMediaPlayer.Error:
            logger.error("播放错误: %s", self.media_player.errorString())
        self._refresh_history_list()

    def _on_media_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        """播放错误"""
        if error != QMediaPlayer.Error.NoError:
            logger.error("播放错误: %s - %s", error, error_string)'''

new_pos = '''    def _on_position_changed(self, position_ms: int) -> None:
        """播放位置变化 → 更新字幕（由 _poll_vlc_state 调用）"""
        # 滑块 + 时间标签：始终实时
        if not self.position_slider.isSliderDown():
            self.position_slider.setValue(position_ms)
        duration = self._vlc_player.get_length()
        self.time_label.setText(
            f"{self._format_time(position_ms)} / {self._format_time(duration)}"
        )

        # ── 字幕同步：节流 ≥ 80ms ──
        last = self._sync_last_pos_ms
        delta = position_ms - last if last >= 0 else 999999
        is_seek = (delta < 0) or (delta > 500)
        if not is_seek and delta < 80:
            return
        self._sync_last_pos_ms = position_ms

        if self._subtitle_entries:
            idx = TranscriberWorker.get_current_entry_index(
                self._subtitle_entries, position_ms
            )
            if idx >= 0:
                self._highlight_subtitle_row(idx)
            else:
                self._highlight_subtitle_row(-1)
        else:
            self._highlight_subtitle_row(-1)

    def _on_duration_changed(self, duration: int) -> None:
        """视频时长变化（由 _poll_vlc_state 调用）"""
        if duration <= 0:
            return
        if self.position_slider.maximum() != duration:
            self.position_slider.setRange(0, duration)
        if self._subtitle_entries:
            needs_rebuild = any(e.start_sec == 0.0 and e.end_sec == 0.0 for e in self._subtitle_entries)
            if needs_rebuild:
                self._distribute_time_axis(duration / 1000.0)
                self._populate_subtitle_list()

    def _on_vlc_state_changed(self, new_state: vlc.State) -> None:
        """VLC 播放状态变化（由 _poll_vlc_state 调用）"""
        if new_state == vlc.State.Playing:
            self.play_btn.setText("⏸ 暂停")
        elif new_state == vlc.State.Paused:
            self.play_btn.setText("▶ 播放")
        elif new_state == vlc.State.Stopped or new_state == vlc.State.Ended:
            self.play_btn.setText("▶ 播放")
            self._highlight_subtitle_row(-1)
        elif new_state == vlc.State.Error:
            media = self._vlc_player.get_media()
            src = media.get_mrl() if media else "未知"
            logger.error("VLC 播放错误，源: %s", src)
        self._refresh_history_list()

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

    def _on_player_error(self, msg: str) -> None:
        logger.error("播放错误: %s", msg)'''

c = rep(c, old_pos, new_pos, 'R4')

# ── R5: _toggle_playback: media_player → _vlc_player ──
c = rep(c,
    '            self.media_player.play()',
    '            self._vlc_player.play()',
    'R5a')
c = rep(c,
    '            self.media_player.pause()',
    '            self._vlc_player.pause()',
    'R5b')

# ── R6: _load_video: setSource → set_media ──
c = rep(c,
    '        self.media_player.setSource(file_path)',
    '        media = self._vlc_instance.media_new(file_path)\n        self._vlc_player.set_media(media)',
    'R6')

# ── R7: _stop_playback ──
c = rep(c,
    '        self.media_player.stop()',
    '        self._vlc_player.stop()',
    'R7')

# ── R8: _seek_position ──
c = rep(c,
    '        self.media_player.setPosition(position)',
    '        self._vlc_player.set_time(position)',
    'R8')

# ── R9: 移除 current_subtitle_label 所有引用 ──
c = rep(c, '        # 隐藏当前字幕\n        self.current_subtitle_label.setVisible(False)', '', 'R9')

# ── R10: _load_video 中启用 _vlc_player 控件 ──
c = rep(c,
    '        self.position_slider.setEnabled(True)',
    '        self.position_slider.setEnabled(True)\n        self.volume_slider.setEnabled(True)\n        self.volume_up_btn.setEnabled(True)\n        self.volume_down_btn.setEnabled(True)',
    'R10')

# ── R11: _stop_playback 中禁用控件 ──
c = rep(c,
    '        self.position_slider.setValue(0)',
    '        self.position_slider.setValue(0)\n        self.volume_slider.setEnabled(False)\n        self.volume_up_btn.setEnabled(False)\n        self.volume_down_btn.setEnabled(False)',
    'R11')

# ── R12: 添加进度条点击 + 音量控制 UI ──
c = rep(c,
    '        self.position_slider.setFixedHeight(20)\n        control_layout.addWidget(self.position_slider, stretch=1)',
    '        self.position_slider.setFixedHeight(20)\n        self.position_slider.setPageStep(0)\n        self.position_slider.mousePressEvent = lambda e: self._on_slider_click(e, self.position_slider)\n        control_layout.addWidget(self.position_slider, stretch=1)\n\n        self.time_label = QLabel("00:00 / 00:00")\n        self.time_label.setFixedWidth(110)\n        self.time_label.setStyleSheet("color: #1565C0; font-size: 12px; background: transparent;")\n        control_layout.addWidget(self.time_label)\n\n        # 音量控制\n        volume_layout = QHBoxLayout()\n        volume_layout.setSpacing(4)\n        self.volume_down_btn = QPushButton("-")\n        self.volume_down_btn.setFixedSize(26, 26)\n        self.volume_down_btn.setStyleSheet("QPushButton { background-color: #90CAF9; border: none; border-radius: 4px; color: white; font-size: 14px; font-weight: bold; } QPushButton:hover { background-color: #42A5F5; } QPushButton:disabled { background-color: #E3F2FD; color: #90CAF9; }")\n        self.volume_down_btn.clicked.connect(self._adjust_volume_down)\n        self.volume_down_btn.setEnabled(False)\n        self.volume_slider = QSlider(Qt.Orientation.Horizontal)\n        self.volume_slider.setRange(0, 100)\n        self.volume_slider.setValue(80)\n        self.volume_slider.setFixedWidth(80)\n        self.volume_slider.setEnabled(False)\n        self.volume_slider.setStyleSheet("QSlider::groove:horizontal { height: 4px; background: #BBDEFB; border-radius: 2px; } QSlider::handle:horizontal { width: 10px; background: #42A5F5; border-radius: 5px; margin: -3px 0; } QSlider::sub-page:horizontal { background: #42A5F5; border-radius: 2px; }")\n        self.volume_slider.valueChanged.connect(self._on_volume_slider_changed)\n        self.volume_up_btn = QPushButton("+")\n        self.volume_up_btn.setFixedSize(26, 26)\n        self.volume_up_btn.setStyleSheet("QPushButton { background-color: #90CAF9; border: none; border-radius: 4px; color: white; font-size: 14px; font-weight: bold; } QPushButton:hover { background-color: #42A5F5; } QPushButton:disabled { background-color: #E3F2FD; color: #90CAF9; }")\n        self.volume_up_btn.clicked.connect(self._adjust_volume_up)\n        self.volume_up_btn.setEnabled(False)\n        volume_layout.addWidget(self.volume_down_btn)\n        volume_layout.addWidget(self.volume_slider)\n        volume_layout.addWidget(self.volume_up_btn)\n        control_layout.addLayout(volume_layout)',
    'R12')

# ── R13: 字幕开关按钮（初始禁用）─
c = rep(c,
    '        self.subtitle_toggle_btn.setEnabled(False)\n        self.subtitle_toggle_btn.clicked.connect(self._toggle_subtitle_display)\n        self._subtitle_panel_visible = True\n        control_layout.addWidget(self.subtitle_toggle_btn)',
    '        self.subtitle_toggle_btn.clicked.connect(self._toggle_subtitle_display)\n        self.subtitle_toggle_btn.setEnabled(False)\n        self._subtitle_panel_visible = True\n        control_layout.addWidget(self.subtitle_toggle_btn)',
    'R13')

# ── R14: time_label 重复创建（前面 R12 已经创建了）─
# 移除旧 time_label 创建
c = rep(c,
    '        self.time_label = QLabel("00:00 / 00:00")\n        self.time_label.setFixedWidth(110)\n        self.time_label.setStyleSheet("color: #1565C0; font-size: 12px; background: transparent;")\n        control_layout.addWidget(self.time_label)',
    '',
    'R14')

# ── R15: 历史面板最小宽度 ──
c = rep(c,
    '        history_panel = QWidget()',
    '        history_panel = QWidget()\n        history_panel.setMinimumWidth(180)',
    'R15')

# ── R16: QSplitter 配置 ──
c = rep(c,
    'content_splitter.setStyleSheet("QSplitter::handle { width: 2px; background: #90CAF9; }")',
    'content_splitter.setStyleSheet("QSplitter::handle { width: 4px; background: #90CAF9; border-radius: 2px; }")\n        content_splitter.setCollapsible(0, False)\n        content_splitter.setHandleWidth(4)',
    'R16')

# ── R17: _add_to_history 不置顶 ──
new_add_history = '''    def _add_to_history(self, title: str, file_path: str, duration: Optional[int] = None) -> None:
        """添加视频到历史记录（去重，不改变原有顺序，只更新元数据）"""
        file_path = os.path.abspath(file_path)

        # 查找是否已存在（不改变列表顺序）
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
            # 已存在：原地更新元数据，不改变列表顺序
            self._video_history[existing_idx].update(entry)
        else:
            # 新视频：追加到末尾（不置顶，保持原有顺序）
            self._video_history.append(entry)

        self._video_history = self._video_history[:100]

        self._refresh_history_list()
        self._save_history()'''

c = rep(c,
    '    def _add_to_history(self, title: str, file_path: str, duration: Optional[int] = None) -> None:\n        """添加视频到历史记录（去重，最新的放最前面）"""',
    new_add_history.split('\n')[0] + '\n        """添加视频到历史记录（去重，不改变原有顺序，只更新元数据）"""',
    'R17')

# Replace the entire method body
old_add_body = '''        file_path = os.path.abspath(file_path)

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
        self._save_history()'''

new_add_body = new_add_history.split('\n        self._refresh_history_list')[0].split(new_add_history.split('\n')[0])[1]

c = rep(c, old_add_body, new_add_body.split('\n        self._refresh_history_list')[0].split('\n        file_path')[1], 'R17b')

# ── R18: 新增方法（插在 _toggle_subtitle_display 之前）─
new_methods = '''
    # ── 进度条点击定位 ─────────────────────────────────────────────────
    def _on_slider_click(self, event, slider):
        """进度条任意位置点击时精准跳转"""
        if slider.maximum() == 0:
            return
        val = slider.minimum() + (slider.maximum() - slider.minimum()) * event.position().x() / slider.width()
        pos = int(val)
        slider.setValue(pos)
        self._seek_position(pos)

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

toggle_idx = c.find('    def _toggle_subtitle_display(self)')
if toggle_idx >= 0:
    lines = c.split('\n')
    for i in range(len(lines)):
        if '    def _toggle_subtitle_display(self)' in lines[i]:
            lines.insert(i, new_methods)
            break
    c = '\n'.join(lines)
    print('  [R18] new methods inserted')

# ── R19: _toggle_subtitle_display 改为控制 subtitle_panel ──
old_toggle = '''    def _toggle_subtitle_display(self) -> None:
        """字幕显示/隐藏开关"""
        self._subtitle_panel_visible = not self._subtitle_panel_visible
        self.subtitle_panel.setVisible(self._subtitle_panel_visible)
        if self._subtitle_panel_visible:
            self.subtitle_toggle_btn.setText("关字幕")
            self.subtitle_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #EF5350; border: none; border-radius: 6px;
                    color: white; font-size: 12px; font-weight: bold;
                }
                QPushButton:hover { background-color: #E53935; }
            """)
        else:
            self.subtitle_toggle_btn.setText("开字幕")
            self.subtitle_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #66BB6A; border: none; border-radius: 6px;
                    color: white; font-size: 12px; font-weight: bold;
                }
                QPushButton:hover { background-color: #43A047; }
            """)'''

new_toggle = '''    def _toggle_subtitle_display(self) -> None:
        """字幕文本区显示/隐藏开关"""
        self._subtitle_panel_visible = not self._subtitle_panel_visible
        self.subtitle_panel.setVisible(self._subtitle_panel_visible)
        if self._subtitle_panel_visible:
            self.subtitle_toggle_btn.setText("关字幕")
            self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #EF5350; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #E53935; }")
        else:
            self.subtitle_toggle_btn.setText("开字幕")
            self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #66BB6A; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #43A047; }")'''

c = rep(c, old_toggle, new_toggle, 'R19')

# ── R20: subtitle_panel 需要是 self 属性 ──
c = rep(c,
    '        subtitle_panel = QWidget()\n        subtitle_panel.setStyleSheet(',
    '        self.subtitle_panel = QWidget()\n        self.subtitle_panel.setStyleSheet(',
    'R20')
c = rep(c,
    '        subtitle_layout = QVBoxLayout(subtitle_panel)',
    '        subtitle_layout = QVBoxLayout(self.subtitle_panel)',
    'R20b')
c = rep(c,
    '        right_layout.addWidget(subtitle_panel)',
    '        right_layout.addWidget(self.subtitle_panel)',
    'R20c')

# ── R21: _load_video 中重置字幕开关 ──
old_reset = '''        # 启用播放控制
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.position_slider.setEnabled(True)
        self.volume_slider.setEnabled(True)
        self.volume_up_btn.setEnabled(True)
        self.volume_down_btn.setEnabled(True)'''
new_reset = '''        # 重置字幕开关状态
        self._subtitle_panel_visible = True
        self.subtitle_panel.setVisible(True)
        self.subtitle_toggle_btn.setEnabled(True)
        self.subtitle_toggle_btn.setText("关字幕")
        self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #EF5350; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #E53935; }")

        # 启用播放控制
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.position_slider.setEnabled(True)
        self.volume_slider.setEnabled(True)
        self.volume_up_btn.setEnabled(True)
        self.volume_down_btn.setEnabled(True)'''

c = rep(c, old_reset, new_reset, 'R21')

# ── R22: _stop_playback 中禁用字幕开关 ──
c = rep(c,
    '        self.position_slider.setValue(0)\n        self.volume_slider.setEnabled(False)\n        self.volume_up_btn.setEnabled(False)\n        self.volume_down_btn.setEnabled(False)',
    '        self.position_slider.setValue(0)\n        self.volume_slider.setEnabled(False)\n        self.volume_up_btn.setEnabled(False)\n        self.volume_down_btn.setEnabled(False)\n        self.subtitle_toggle_btn.setEnabled(False)',
    'R22')

# ── R23: 移除所有 QVideoWidget 引用 ──
c = rep(c,
    '        self.video_widget = QVideoWidget()',
    '        self.video_widget = QWidget()',
    'R23')

# ── R24: 移除 QAudioOutput ──
c = rep(c,
    '        self.audio_output = QAudioOutput()\n        self.media_player.setAudioOutput(self.audio_output)\n        self.media_player.setVideoOutput(self.video_widget)\n\n        self.media_player.positionChanged.connect',
    '        # VLC 无需 QAudioOutput/QVideoOutput，轮询处理\n\n        self.media_player.positionChanged.connect',
    'R24')

# ── R25: closeEvent 中释放 VLC ──
c = rep(c,
    '        self.media_player.stop()',
    '        if hasattr(self, "_vlc_player") and self._vlc_player:\n            self._vlc_player.stop()\n        if hasattr(self, "_vlc_instance") and self._vlc_instance:\n            self._vlc_instance.release()',
    'R25')

# Final check
check(c, 'FINAL')

save(c)
print('Done.')
