#!/usr/bin/env python3
"""完整迁移：QMediaPlayer → VLC + 全部新功能"""
import ast, sys

PATH = 'gui/main_window.py'

def load(): return open(PATH, encoding='utf-8').read()
def save(c): open(PATH, 'w', encoding='utf-8').write(c)

def verify(c, tag):
    try:
        ast.parse(c)
        print(f'  [{tag}] OK')
        return True
    except SyntaxError as e:
        print(f'  [{tag}] ERROR line {e.lineno}: {e.msg}')
        return False

def lreplace(lines, start, end, new_lines):
    return lines[:start] + new_lines + lines[end:]

def find(c, text, after=0):
    for i, l in enumerate(c.split('\n')):
        if i >= after and text in l:
            return i
    return -1

c = load()
lines = c.split('\n')

# ── 1. import ──
i = find(c, 'from PySide6.QtMultimedia import QMediaPlayer')
lines[i] = 'import vlc  # VLC 播放器'
i = find(c, 'from PySide6.QtMultimediaWidgets import QVideoWidget')
lines[i] = '# removed QVideoWidget (migrated to VLC)'
c = '\n'.join(lines)
verify(c, '1')

# ── 2. video_widget ──
i = find(c, 'self.video_widget = QVideoWidget()')
lines = c.split('\n')
lines[i] = '        self.video_widget = QWidget()'
c = '\n'.join(lines)
verify(c, '2')

# ── 3. _setup_media_player 重写 ──
# Find the method body (lines 669 to next method)
i669 = find(c, '    def _setup_media_player(self) -> None:')
i670 = find(c, '        """初始化 QMediaPlayer', i669)
i671 = find(c, '        self.audio_output = QAudioOutput()')
i672 = find(c, '        self.media_player = QMediaPlayer()')
i673 = find(c, '        self.media_player.setAudioOutput', i672)
i674 = find(c, '        self.media_player.durationChanged.connect')  # last setup line
print(f'  [3] setup: {i669}-{i674}')
new_setup = '''    def _setup_media_player(self) -> None:
        """初始化 VLC 媒体播放器"""
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
        if sys.platform == "win32":
            self._vlc_player.set_hwnd(self.video_widget.winId())
        elif sys.platform == "darwin":
            self._vlc_player.set_nsobject(int(self.video_widget.winId()))
        self._vlc_player.audio_set_volume(80)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(80)
        self._poll_timer.timeout.connect(self._poll_vlc_state)
        self._poll_timer.start()
        self._vlc_prev_state = None
        self._vlc_prev_media = None'''
lines = c.split('\n')
lines = lreplace(lines, i669, i674+1, new_setup.split('\n'))
c = '\n'.join(lines)
verify(c, '3')

# ── 4. 移除 media_player 信号连接 ──
i_sig1 = find(c, 'self.media_player.positionChanged.connect')
i_sig2 = find(c, 'self.media_player.mediaStatusChanged.connect')
print(f'  [4] signals: {i_sig1}-{i_sig2}')
lines = c.split('\n')
# Replace the range with one comment line
lines = lreplace(lines, i_sig1, i_sig2+1, ['        # VLC 状态通过 _poll_timer 轮询，不需要 Qt 信号'])
c = '\n'.join(lines)
verify(c, '4')

# ── 5. 进度条鼠标点击 ──
i = find(c, 'self.position_slider.setFixedHeight(20)')
lines = c.split('\n')
lines[i] = '        self.position_slider.setFixedHeight(20)\n        self.position_slider.setPageStep(0)\n        self.position_slider.mousePressEvent = lambda e: self._on_slider_click(e, self.position_slider)'
c = '\n'.join(lines)
verify(c, '5')

# ── 6. time_label 后插音量控制 ──
i = find(c, 'control_layout.addWidget(self.time_label)')
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
        control_layout.addLayout(volume_layout)'''
lines = c.split('\n')
lines.insert(i+1, vol)
c = '\n'.join(lines)
verify(c, '6')

# ── 7. subtitle_panel self 属性 ──
c = c.replace('        subtitle_panel = QWidget()', '        self.subtitle_panel = QWidget()', 1)
c = c.replace('subtitle_layout = QVBoxLayout(subtitle_panel)', 'subtitle_layout = QVBoxLayout(self.subtitle_panel)', 1)
c = c.replace('right_layout.addWidget(subtitle_panel)', 'right_layout.addWidget(self.subtitle_panel)', 1)
print('  [7] subtitle_panel self attr')
verify(c, '7')

# ── 8. subtitle_toggle_btn 初始禁用 ──
i = find(c, 'self.subtitle_toggle_btn.setEnabled(False)')
lines = c.split('\n')
lines[i] = '        self.subtitle_toggle_btn.clicked.connect(self._toggle_subtitle_display)\n        self.subtitle_toggle_btn.setEnabled(False)\n        self._subtitle_panel_visible = True'
c = '\n'.join(lines)
print('  [8] subtitle toggle init')
verify(c, '8')

# ── 9. history_panel 最小宽度 ──
i = find(c, '        history_panel = QWidget()')
lines = c.split('\n')
lines.insert(i+1, "        history_panel.setMinimumWidth(180)")
c = '\n'.join(lines)
print('  [9] history min width')
verify(c, '9')

# ── 10. QSplitter handle 样式 ──
i = find(c, 'content_splitter.setStyleSheet')
lines = c.split('\n')
lines[i] = '        content_splitter.setStyleSheet("QSplitter::handle { width: 4px; background: #90CAF9; border-radius: 2px; }")'
c = '\n'.join(lines)
print('  [10] splitter style')
verify(c, '10')

# ── 11. _toggle_playback ──
c = c.replace('self.media_player.play()', 'self._vlc_player.play()', 1)
c = c.replace('self.media_player.pause()', 'self._vlc_player.pause()', 1)
print('  [11] toggle_playback')
verify(c, '11')

# ── 12. _load_video: setSource → VLC ──
i = find(c, 'self.media_player.setSource')
lines = c.split('\n')
for i2 in range(i, min(i+3, len(lines))):
    if 'self.media_player.setSource' in lines[i2]:
        lines[i2] = '        media = self._vlc_instance.media_new(file_path)\n        self._vlc_player.set_media(media)'
        break
c = '\n'.join(lines)
print('  [12] _load_video VLC')
verify(c, '12')

# ── 13. _load_video 启用控件 ──
# Find position_slider.setEnabled(True) in _load_video
i = find(c, 'self.position_slider.setEnabled(True)')
lines = c.split('\n')
# Only replace the first occurrence (in _load_video)
lines[i] = lines[i] + '\n        self.volume_slider.setEnabled(True)\n        self.volume_up_btn.setEnabled(True)\n        self.volume_down_btn.setEnabled(True)'
c = '\n'.join(lines)
print('  [13] volume enable')
verify(c, '13')

# ── 14. _load_video 重置字幕开关 ──
i = find(c, 'self.volume_slider.setEnabled(True)')  # just added in 13
lines = c.split('\n')
lines.insert(i+1,
    '        self._subtitle_panel_visible = True\n'
    '        self.subtitle_panel.setVisible(True)\n'
    '        self.subtitle_toggle_btn.setEnabled(True)\n'
    '        self.subtitle_toggle_btn.setText("关字幕")\n'
    '        self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #EF5350; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #E53935; }")')
c = '\n'.join(lines)
print('  [14] subtitle toggle reset')
verify(c, '14')

# ── 15. _stop_playback ──
i = find(c, 'self.media_player.stop()')
lines = c.split('\n')
lines[i] = '        self._vlc_player.stop()'
c = '\n'.join(lines)
print('  [15] stop')
verify(c, '15')

# ── 16. _stop_playback 禁用控件 ──
i = find(c, 'self.position_slider.setValue(0)')
lines = c.split('\n')
lines.insert(i+1,
    '        self.volume_slider.setEnabled(False)\n'
    '        self.volume_up_btn.setEnabled(False)\n'
    '        self.volume_down_btn.setEnabled(False)\n'
    '        self.subtitle_toggle_btn.setEnabled(False)')
c = '\n'.join(lines)
print('  [16] disable controls')
verify(c, '16')

# ── 17. _seek_position ──
c = c.replace('self.media_player.setPosition(position)', 'self._vlc_player.set_time(position)', 1)
print('  [17] seek')
verify(c, '17')

# ── 18. _on_state_changed ──
i = find(c, 'def _on_state_changed(self, state: QMediaPlayer.PlaybackState)')
lines = c.split('\n')
lines[i] = '    def _on_vlc_state_changed(self, new_state: vlc.State) -> None:'
c = '\n'.join(lines)
c = c.replace('if state == QMediaPlayer.PlaybackState.PlayingState:', 'if new_state == vlc.State.Playing:')
c = c.replace('elif state == QMediaPlayer.PlaybackState.PausedState:', 'elif new_state == vlc.State.Paused:')
c = c.replace('elif state == QMediaPlayer.PlaybackState.StoppedState:', 'elif new_state == vlc.State.Stopped or new_state == vlc.State.Ended:')
c = c.replace('self.current_subtitle_label.setVisible(False)', '# removed (blue label)')
print('  [18] _on_state_changed VLC')
verify(c, '18')

# ── 19. _poll_vlc_state 新增 ──
i = find(c, '    def _on_vlc_state_changed')
lines = c.split('\n')
poll = '''
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
lines.insert(i, poll)
c = '\n'.join(lines)
print('  [19] _poll_vlc_state')
verify(c, '19')

# ── 20. _on_position_changed duration ──
c = c.replace('self.media_player.duration()', 'self._vlc_player.get_length()', 1)
print('  [20] position_changed VLC')
verify(c, '20')

# ── 21. _on_media_status_changed 简化 ──
i = find(c, 'def _on_media_status_changed')
end = i + 1
while end < len(c.split('\n')):
    if c.split('\n')[end].startswith('    def ') and '_on_media_status' not in c.split('\n')[end]:
        break
    end += 1
lines = c.split('\n')
lines = lreplace(lines, i, end, ['    def _on_media_status_changed(self, status) -> None:', '        """VLC 不需要，状态由 _poll_vlc_state 处理"""', '        pass'])
c = '\n'.join(lines)
print('  [21] media_status simplified')
verify(c, '21')

# ── 22. _on_player_error 简化 ──
i = find(c, 'def _on_player_error')
end = i + 1
while end < len(c.split('\n')):
    if c.split('\n')[end].startswith('    def ') and '_on_player_error' not in c.split('\n')[end]:
        break
    end += 1
lines = c.split('\n')
lines = lreplace(lines, i, end, ['    def _on_player_error(self, msg: str) -> None:', '        logger.error("播放错误: %s", msg)'])
c = '\n'.join(lines)
print('  [22] player_error simplified')
verify(c, '22')

# ── 23. _add_to_history 不置顶 ──
i = find(c, 'def _add_to_history(self, title: str')
end = find(c, '    def _refresh_history_list', i)
lines = c.split('\n')
new_m = [
    '    def _add_to_history(self, title: str, file_path: str, duration: Optional[int] = None) -> None:',
    '        """添加视频到历史记录（去重，不改变原有顺序，只更新元数据）"""',
    '        file_path = os.path.abspath(file_path)',
    '',
    '        existing_idx = None',
    '        for i2, h in enumerate(self._video_history):',
    '            if h.get("path") == file_path:',
    '                existing_idx = i2',
    '                break',
    '',
    '        safe_fallback = os.path.splitext(os.path.basename(file_path))[0]',
    '        if safe_fallback.lower() in ("stream", "视频"):',
    '            safe_fallback = (self._video_history[existing_idx].get("title", "视频")',
    '                            if existing_idx is not None else "视频")',
    '',
    '        entry = {',
    '            "title": (title or',
    '                      (self._video_history[existing_idx].get("title", safe_fallback)',
    '                       if existing_idx is not None else safe_fallback)),',
    '            "path": file_path,',
    '            "duration": (duration if duration is not None else',
    '                         (self._video_history[existing_idx].get("duration")',
    '                          if existing_idx is not None else None)),',
    '            "time": time.strftime("%Y-%m-%d %H:%M"),',
    '        }',
    '        entry.pop("source", None)',
    '',
    '        if existing_idx is not None:',
    '            self._video_history[existing_idx].update(entry)',
    '        else:',
    '            self._video_history.append(entry)',
    '',
    '        self._video_history = self._video_history[:100]',
    '',
    '        self._refresh_history_list()',
    '        self._save_history()',
    '',
]
lines = lreplace(lines, i, end, new_m)
c = '\n'.join(lines)
print('  [23] _add_to_history')
verify(c, '23')

# ── 24. _toggle_subtitle_display ──
i = find(c, 'def _toggle_subtitle_display(self)')
end = i + 1
while end < len(c.split('\n')):
    if c.split('\n')[end].startswith('    def ') and '_toggle_subtitle' not in c.split('\n')[end]:
        break
    end += 1
lines = c.split('\n')
new_t = [
    '    def _toggle_subtitle_display(self) -> None:',
    '        """字幕文本区显示/隐藏开关"""',
    '        self._subtitle_panel_visible = not self._subtitle_panel_visible',
    '        self.subtitle_panel.setVisible(self._subtitle_panel_visible)',
    '        if self._subtitle_panel_visible:',
    '            self.subtitle_toggle_btn.setText("关字幕")',
    '            self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #EF5350; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #E53935; }")',
    '        else:',
    '            self.subtitle_toggle_btn.setText("开字幕")',
    '            self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #66BB6A; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #43A047; }")',
    '',
]
lines = lreplace(lines, i, end, new_t)
c = '\n'.join(lines)
print('  [24] toggle_subtitle_display')
verify(c, '24')

# ── 25. 新增辅助方法 ──
i = find(c, '    def _toggle_subtitle_display')
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
lines = c.split('\n')
lines.insert(i, helpers)
c = '\n'.join(lines)
print('  [25] helpers')
verify(c, '25')

# ── 26. closeEvent ──
i = find(c, 'def closeEvent(self, event)')
if i >= 0:
    lines = c.split('\n')
    for j in range(i, min(i+5, len(lines))):
        if 'self.media_player.stop()' in lines[j]:
            lines[j] = '            if hasattr(self, "_vlc_player") and self._vlc_player:\n                self._vlc_player.stop()\n            if hasattr(self, "_vlc_instance") and self._vlc_instance:\n                self._vlc_instance.release()'
            break
    c = '\n'.join(lines)
    print('  [26] closeEvent')

# Final
if verify(c, 'FINAL'):
    save(c)
    print('\nAll 26 patches applied successfully.')
else:
    sys.exit(1)
