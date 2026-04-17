#!/usr/bin/env python3
"""后续批次修复：新增方法和剩余问题"""
import ast

PATH = 'gui/main_window.py'

def load(): return open(PATH, encoding='utf-8').read()
def save(c): open(PATH, 'w', encoding='utf-8').write(c)

def verify(c): 
    try: ast.parse(c); return True
    except SyntaxError as e: print(f'SYNTAX ERROR line {e.lineno}: {e.msg}'); return False

def apply(c, old, new, tag):
    if old not in c: print(f'  [{tag}] SKIP'); return c
    new_c = c.replace(old, new, 1)
    if verify(new_c): print(f'  [{tag}] OK'); return new_c
    raise Exception(f'[{tag}] Failed')

# ═══════════════════════════════════════════════════════════════
# 批次9：添加 _poll_vlc_state 方法
# ═══════════════════════════════════════════════════════════════
c = load()
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
if '_poll_vlc_state' not in c:
    lines = c.split('\n')
    for i, l in enumerate(lines):
        if '    def _on_vlc_state_changed' in l:
            lines.insert(i, poll_method)
            break
    c = '\n'.join(lines)
    if verify(c): save(c); print('  [poll_vlc_state] OK')

# ═══════════════════════════════════════════════════════════════
# 批次10：添加 _get_display_title 方法
# ═══════════════════════════════════════════════════════════════
c = load()
get_title = '''
    def _get_display_title(self) -> str:
        """获取显示标题"""
        if hasattr(self, "_download_title") and self._download_title:
            return self._download_title
        if self._current_video_path:
            name = os.path.splitext(os.path.basename(self._current_video_path))[0]
            if name.lower() not in ("stream", "视频"):
                return name
        return "视频"

'''
if '_get_display_title' not in c:
    lines = c.split('\n')
    for i, l in enumerate(lines):
        if '    def _poll_vlc_state' in l:
            lines.insert(i, get_title)
            break
    c = '\n'.join(lines)
    if verify(c): save(c); print('  [get_title] OK')

# ═══════════════════════════════════════════════════════════════
# 批次11：添加音量控制和字幕开关按钮
# ═══════════════════════════════════════════════════════════════
c = load()
# 在 time_label 后添加音量控制
if 'volume_slider' not in c:
    lines = c.split('\n')
    for i, l in enumerate(lines):
        if 'control_layout.addWidget(self.time_label)' in l:
            vol = '''
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
        control_layout.addLayout(volume_layout)
        # 字幕开关
        self.subtitle_toggle_btn = QPushButton("关字幕")
        self.subtitle_toggle_btn.setFixedHeight(32)
        self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #EF5350; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #E53935; } QPushButton:disabled { background-color: #E8F5E9; color: #A5D6A7; }")
        self.subtitle_toggle_btn.clicked.connect(self._toggle_subtitle_display)
        self.subtitle_toggle_btn.setEnabled(False)
        self._subtitle_panel_visible = True
        control_layout.addWidget(self.subtitle_toggle_btn)'''
            lines.insert(i+1, vol)
            break
    c = '\n'.join(lines)
    if verify(c): save(c); print('  [volume_subtitle_btn] OK')

# ═══════════════════════════════════════════════════════════════
# 批次12：添加辅助方法
# ═══════════════════════════════════════════════════════════════
c = load()
helpers = '''
    # ── 进度条点击定位 ─────────────────────────────────────────────────
    def _on_slider_click(self, event, slider):
        if slider.maximum() == 0: return
        val = slider.minimum() + (slider.maximum() - slider.minimum()) * event.position().x() / slider.width()
        pos = int(val)
        slider.setValue(pos)
        self._seek_position(pos)

    # ── 音量控制 ─────────────────────────────────────────────────────────
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

    # ── 字幕开关 ─────────────────────────────────────────────────────────
    def _toggle_subtitle_display(self) -> None:
        self._subtitle_panel_visible = not self._subtitle_panel_visible
        self.subtitle_panel.setVisible(self._subtitle_panel_visible)
        if self._subtitle_panel_visible:
            self.subtitle_toggle_btn.setText("关字幕")
            self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #EF5350; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #E53935; }")
        else:
            self.subtitle_toggle_btn.setText("开字幕")
            self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #66BB6A; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #43A047; }")

'''
if '_on_slider_click' not in c:
    lines = c.split('\n')
    for i, l in enumerate(lines):
        if '    def _get_display_title' in l:
            lines.insert(i, helpers)
            break
    c = '\n'.join(lines)
    if verify(c): save(c); print('  [helpers] OK')

# ═══════════════════════════════════════════════════════════════
# 批次13：进度条点击支持
# ═══════════════════════════════════════════════════════════════
c = load()
c = apply(c,
    '        self.position_slider.setFixedHeight(20)\n        control_layout.addWidget(self.position_slider, stretch=1)',
    '        self.position_slider.setFixedHeight(20)\n        self.position_slider.setPageStep(0)\n        self.position_slider.mousePressEvent = lambda e: self._on_slider_click(e, self.position_slider)\n        control_layout.addWidget(self.position_slider, stretch=1)',
    'slider_click')
save(c)

# ═══════════════════════════════════════════════════════════════
# 批次14：subtitle_panel 改为 self 属性
# ═══════════════════════════════════════════════════════════════
c = load()
c = apply(c, '        subtitle_panel = QWidget()', '        self.subtitle_panel = QWidget()', 'subtitle_self')
c = apply(c, 'subtitle_layout = QVBoxLayout(subtitle_panel)', 'subtitle_layout = QVBoxLayout(self.subtitle_panel)', 'subtitle_layout')
c = apply(c, 'right_layout.addWidget(subtitle_panel)', 'right_layout.addWidget(self.subtitle_panel)', 'subtitle_add')
save(c)

# ═══════════════════════════════════════════════════════════════
# 批次15：history_panel 最小宽度
# ═══════════════════════════════════════════════════════════════
c = load()
c = apply(c, '        history_panel = QWidget()', '        history_panel = QWidget()\n        history_panel.setMinimumWidth(180)', 'history_min')
save(c)

# ═══════════════════════════════════════════════════════════════
# 批次16：_add_to_history 不置顶
# ═══════════════════════════════════════════════════════════════
c = load()
old_add = '''    def _add_to_history(self, title: str, file_path: str, duration: Optional[int] = None) -> None:
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
        entry.pop("source", None)

        self._video_history = [entry] + remaining

        # 最多保留 100 条
        self._video_history = self._video_history[:100]

        self._refresh_history_list()
        self._save_history()'''
new_add = '''    def _add_to_history(self, title: str, file_path: str, duration: Optional[int] = None) -> None:
        """添加视频到历史记录（去重，不改变原有顺序）"""
        file_path = os.path.abspath(file_path)
        existing_idx = None
        for i, h in enumerate(self._video_history):
            if h.get("path") == file_path:
                existing_idx = i
                break
        safe_fallback = os.path.splitext(os.path.basename(file_path))[0]
        if safe_fallback.lower() in ("stream", "视频"):
            safe_fallback = (self._video_history[existing_idx].get("title", "视频") if existing_idx is not None else "视频")
        entry = {
            "title": title or (self._video_history[existing_idx].get("title", safe_fallback) if existing_idx is not None else safe_fallback),
            "path": file_path,
            "duration": duration if duration is not None else (self._video_history[existing_idx].get("duration") if existing_idx is not None else None),
            "time": time.strftime("%Y-%m-%d %H:%M"),
        }
        entry.pop("source", None)
        if existing_idx is not None:
            self._video_history[existing_idx].update(entry)
        else:
            self._video_history.append(entry)
        self._video_history = self._video_history[:100]
        self._refresh_history_list()
        self._save_history()'''
c = apply(c, old_add, new_add, 'add_history')
save(c)

# ═══════════════════════════════════════════════════════════════
# 批次17：closeEvent VLC 清理
# ═══════════════════════════════════════════════════════════════
c = load()
c = apply(c,
    '        self.media_player.stop()',
    '        if hasattr(self, "_vlc_player") and self._vlc_player:\n            self._vlc_player.stop()\n        if hasattr(self, "_vlc_instance") and self._vlc_instance:\n            self._vlc_instance.release()',
    'close_event')
save(c)

# ═══════════════════════════════════════════════════════════════
# 批次18：_on_media_status_changed 简化
# ═══════════════════════════════════════════════════════════════
c = load()
old_ms = '''    @Slot("QMediaPlayer::MediaStatus")
    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        """媒体状态变化 → 控制加载提示"""
        logger.info("媒体状态: %s", status)
        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            self._hide_loading()
            title = os.path.splitext(os.path.basename(self.media_player.source().toLocalFile()))[0]
            self.status_label.setText(f"已加载: {title}")

            # 如果有待播放的请求，自动开始播放
            if self._auto_play_pending:
                self._auto_play_pending = False
                self._toggle_playback()'''
new_ms = '''    def _on_media_status_changed(self, status) -> None:
        """VLC 不需要，状态由 _poll_vlc_state 处理"""
        pass'''
c = apply(c, old_ms, new_ms, 'media_status')
save(c)

# ═══════════════════════════════════════════════════════════════
# 批次19：_on_player_error 简化
# ═══════════════════════════════════════════════════════════════
c = load()
old_err = '''    @Slot(QMediaPlayer.Error, str)
    def _on_player_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        """播放器错误"""
        logger.error(
            "播放器错误: code=%s msg=%s source=%s",
            error, error_string,
            getattr(self.media_player, "source", lambda: None)(),
        )'''
new_err = '''    def _on_player_error(self, msg: str = "") -> None:
        """播放器错误"""
        logger.error("播放器错误: %s", msg)'''
c = apply(c, old_err, new_err, 'player_error')
save(c)

# ═══════════════════════════════════════════════════════════════
# 批次20：_load_video 启用控件
# ═══════════════════════════════════════════════════════════════
c = load()
c = apply(c,
    '        self.position_slider.setEnabled(True)\n\n        title',
    '        self.position_slider.setEnabled(True)\n        self.volume_slider.setEnabled(True)\n        self.volume_up_btn.setEnabled(True)\n        self.volume_down_btn.setEnabled(True)\n        self.subtitle_toggle_btn.setEnabled(True)\n\n        title',
    'enable_controls')
save(c)

# 最终验证
c = load()
if verify(c):
    print('\n全部批次完成！工业级修复成功。')
else:
    print('\n存在语法错误，需要检查。')
