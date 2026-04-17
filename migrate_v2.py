#!/usr/bin/env python3
"""完整重写：从 QMediaPlayer → VLC + 添加所有新功能（精确行号版）"""
import ast, sys

PATH = 'gui/main_window.py'

def load():
    return open(PATH, encoding='utf-8').read()

def save(c):
    open(PATH, 'w', encoding='utf-8').write(c)

def verify(c, tag):
    try:
        ast.parse(c)
        print(f'  [{tag}] OK')
        return True
    except SyntaxError as e:
        print(f'  [{tag}] SYNTAX ERROR line {e.lineno}: {e.msg}')
        return False

def lreplace(lines, start, end, new_lines):
    """Replace lines[start:end] with new_lines"""
    return lines[:start] + new_lines + lines[end:]

def lreplace_after(lines, after_idx, new_lines):
    """Insert new_lines right after line index after_idx"""
    return lines[:after_idx+1] + new_lines + lines[after_idx+1:]

def find_line(c, text, start=0):
    for i, l in enumerate(c.split('\n')):
        if i >= start and text in l:
            return i
    return -1

def find_lines(c, start_text, end_text, start=0):
    """Find start and end line indices for a block"""
    lines = c.split('\n')
    start_i = end_i = -1
    for i in range(start, len(lines)):
        if start_text in lines[i]:
            start_i = i
        if start_i >= 0 and end_i < 0 and i > start_i and lines[i].startswith('    def ') and end_text in lines[i]:
            end_i = i
    return start_i, end_i

c = load()
lines = c.split('\n')
print(f'File: {len(lines)} lines')

# ── 1. imports ──
i52 = find_line(c, 'from PySide6.QtMultimedia import QMediaPlayer')
i53 = find_line(c, 'from PySide6.QtMultimediaWidgets import QVideoWidget')
lines[i52] = 'import vlc  # VLC 播放器'
lines[i53] = '# QVideoWidget/QMediaPlayer/QAudioOutput removed (migrated to VLC)'
c = '\n'.join(lines)
print('  [1] imports')
verify(c, '1')

# ── 2. video_widget: QVideoWidget → QWidget ──
ivw = find_line(c, 'self.video_widget = QVideoWidget()')
lines = c.split('\n')
lines[ivw] = '        self.video_widget = QWidget()'
c = '\n'.join(lines)
print('  [2] video_widget = QWidget')
verify(c, '2')

# ── 3. _setup_media_player: 完全重写 ──
i669 = find_line(c, '    def _setup_media_player(self) -> None:')
i670 = find_line(c, '        """初始化 QMediaPlayer', i669)
i671 = find_line(c, '        self.audio_output = QAudioOutput()')
i672 = find_line(c, '        self.media_player = QMediaPlayer()')
i673 = find_line(c, '        self.media_player.setAudioOutput')
# Find end of _setup_media_player
i674 = find_line(c, '        self.media_player.durationChanged.connect')  # last signal in method

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

        # 将 VLC 视频输出绑定到 QWidget
        if sys.platform == "win32":
            self._vlc_player.set_hwnd(self.video_widget.winId())
        elif sys.platform == "darwin":
            self._vlc_player.set_nsobject(int(self.video_widget.winId()))

        self._vlc_player.audio_set_volume(80)

        # 轮询定时器：VLC 没有 Qt 信号，用定时器轮询状态/进度
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(80)
        self._poll_timer.timeout.connect(self._poll_vlc_state)
        self._poll_timer.start()

        self._vlc_prev_state = None
        self._vlc_prev_media = None'''

lines = c.split('\n')
lines = lreplace(lines, i669, i674+1, new_setup.split('\n'))
c = '\n'.join(lines)
print('  [3] _setup_media_player')
verify(c, '3')

# ── 4. 移除 media_player 信号连接 ──
i_sigs = find_line(c, 'self.media_player.positionChanged.connect')
i_sige = find_line(c, 'self.media_player.mediaStatusChanged.connect')
lines = c.split('\n')
# Remove lines i_sigs through i_sige (inclusive), replace with comment
for i in range(i_sigs, i_sige+1):
    lines[i] = '        # VLC 状态通过 _poll_timer 轮询，不需要 Qt 信号'
c = '\n'.join(lines)
print('  [4] signal connections removed')
verify(c, '4')

# ── 5. position_slider: 添加鼠标点击 + setPageStep ──
ips = find_line(c, 'self.position_slider.setFixedHeight(20)')
lines = c.split('\n')
lines[ips] = '        self.position_slider.setFixedHeight(20)\n        self.position_slider.setPageStep(0)\n        self.position_slider.mousePressEvent = lambda e: self._on_slider_click(e, self.position_slider)'
c = '\n'.join(lines)
print('  [5] position_slider click')
verify(c, '5')

# ── 6. time_label 后插音量控制 ──
itimel = find_line(c, 'control_layout.addWidget(self.time_label)')
volume_code = '''
        # ── 音量控制 ───────────────────────────────────────────────────
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
lines.insert(itimel+1, volume_code)
c = '\n'.join(lines)
print('  [6] volume control')
verify(c, '6')

# ── 7. subtitle_panel: 改为 self 属性 ──
isp = find_line(c, '        subtitle_panel = QWidget()')
lines = c.split('\n')
lines[isp] = '        self.subtitle_panel = QWidget()'
c = '\n'.join(lines)
c = c.replace('subtitle_layout = QVBoxLayout(subtitle_panel)', 'subtitle_layout = QVBoxLayout(self.subtitle_panel)', 1)
c = c.replace('right_layout.addWidget(subtitle_panel)', 'right_layout.addWidget(self.subtitle_panel)', 1)
print('  [7] subtitle_panel self attribute')
verify(c, '7')

# ── 8. subtitle_toggle_btn: 初始禁用 ──
ist = find_line(c, 'self.subtitle_toggle_btn.setEnabled(False)')
if ist >= 0:
    lines = c.split('\n')
    lines[ist] = '        self.subtitle_toggle_btn.clicked.connect(self._toggle_subtitle_display)\n        self.subtitle_toggle_btn.setEnabled(False)\n        self._subtitle_panel_visible = True'
    c = '\n'.join(lines)
print('  [8] subtitle toggle init')
verify(c, '8')

# ── 9. history_panel 最小宽度 ──
ihp = find_line(c, '        history_panel = QWidget()')
lines = c.split('\n')
lines.insert(ihp+1, "        history_panel.setMinimumWidth(180)")
c = '\n'.join(lines)
print('  [9] history min width')
verify(c, '9')

# ── 10. QSplitter handle 样式 ──
isc = find_line(c, 'content_splitter.setStyleSheet')
lines = c.split('\n')
lines[isc] = '        content_splitter.setStyleSheet("QSplitter::handle { width: 4px; background: #90CAF9; border-radius: 2px; }")'
c = '\n'.join(lines)
print('  [10] splitter style')
verify(c, '10')

# ── 11. _toggle_playback: media_player → _vlc_player ──
c = c.replace('self.media_player.play()', 'self._vlc_player.play()', 1)
c = c.replace('self.media_player.pause()', 'self._vlc_player.pause()', 1)
print('  [11] toggle_playback vlc')
verify(c, '11')

# ── 12. _load_video: setSource → VLC ──
i_load = find_line(c, 'def _load_video(self, file_path: str')
i_src = find_line(c, 'self.media_player.setSource')
lines = c.split('\n')
# Replace setSource line
new_src = '        media = self._vlc_instance.media_new(file_path)\n        self._vlc_player.set_media(media)'
for i in range(i_src, len(lines)):
    if 'self.media_player.setSource' in lines[i]:
        lines[i] = new_src
        break
c = '\n'.join(lines)
print('  [12] _load_video VLC')
verify(c, '12')

# ── 13. _load_video 启用控件 ──
i_en = find_line(c, 'self.position_slider.setEnabled(True)')
if i_en >= 0:
    lines = c.split('\n')
    lines.insert(i_en+1,
        '        self.volume_slider.setEnabled(True)\n'
        '        self.volume_up_btn.setEnabled(True)\n'
        '        self.volume_down_btn.setEnabled(True)')
    c = '\n'.join(lines)
    print('  [13] volume enable in _load_video')
verify(c, '13')

# ── 14. _load_video 重置字幕开关 ──
i_en2 = find_line(c, 'self.position_slider.setEnabled(True)')
if i_en2 >= 0:
    lines = c.split('\n')
    lines.insert(i_en2+1,
        '        self._subtitle_panel_visible = True\n'
        '        self.subtitle_panel.setVisible(True)\n'
        '        self.subtitle_toggle_btn.setEnabled(True)\n'
        '        self.subtitle_toggle_btn.setText("关字幕")\n'
        '        self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #EF5350; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #E53935; }")')
    c = '\n'.join(lines)
    print('  [14] subtitle toggle reset')
verify(c, '14')

# ── 15. _stop_playback ──
i_stop = find_line(c, 'self.media_player.stop()')
if i_stop >= 0:
    lines = c.split('\n')
    lines[i_stop] = '        self._vlc_player.stop()'
    c = '\n'.join(lines)
    print('  [15] stop_playback')
verify(c, '15')

# ── 16. _stop_playback 禁用控件 ──
i_sv = find_line(c, 'self.position_slider.setValue(0)')
if i_sv >= 0:
    lines = c.split('\n')
    lines.insert(i_sv+1,
        '        self.volume_slider.setEnabled(False)\n'
        '        self.volume_up_btn.setEnabled(False)\n'
        '        self.volume_down_btn.setEnabled(False)\n'
        '        self.subtitle_toggle_btn.setEnabled(False)')
    c = '\n'.join(lines)
    print('  [16] disable controls in stop')
verify(c, '16')

# ── 17. _seek_position ──
c = c.replace('self.media_player.setPosition(position)', 'self._vlc_player.set_time(position)', 1)
print('  [17] seek_position')
verify(c, '17')

# ── 18. _on_state_changed: QMediaPlayer → VLC ──
i_state = find_line(c, 'def _on_state_changed(self, state: QMediaPlayer.PlaybackState)')
if i_state >= 0:
    lines = c.split('\n')
    new_sig = '    def _on_vlc_state_changed(self, new_state: vlc.State) -> None:'
    lines[i_state] = new_sig
    # Update body
    c = '\n'.join(lines)
    c = c.replace('if state == QMediaPlayer.PlaybackState.PlayingState:', 'if new_state == vlc.State.Playing:')
    c = c.replace('elif state == QMediaPlayer.PlaybackState.PausedState:', 'elif new_state == vlc.State.Paused:')
    c = c.replace('elif state == QMediaPlayer.PlaybackState.StoppedState:', 'elif new_state == vlc.State.Stopped or new_state == vlc.State.Ended:')
    c = c.replace('self.current_subtitle_label.setVisible(False)', '# removed')
    c = c.replace('logger.error("播放错误: %s - %s", error, error_string)', 'logger.error("VLC 播放错误")')
    print('  [18] _on_state_changed VLC')
verify(c, '18')

# ── 19. _poll_vlc_state 新增 ──
i_state2 = find_line(c, 'def _on_state_changed(self,') or find_line(c, 'def _on_vlc_state_changed(self,')
# Insert before _on_state_changed
lines = c.split('\n')
for i in range(len(lines)):
    if 'def _on_vlc_state_changed' in lines[i] or 'def _on_state_changed(self, state: QMediaPlayer' in lines[i]:
        poll_code = '''
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
        lines.insert(i, poll_code)
        break
c = '\n'.join(lines)
print('  [19] _poll_vlc_state')
verify(c, '19')

# ── 20. _on_position_changed: get_duration → VLC ──
c = c.replace('self.media_player.duration()', 'self._vlc_player.get_length()', 1)
print('  [20] _on_position_changed VLC')
verify(c, '20')

# ── 21. _on_media_status_changed: 简化 ──
i_ms = find_line(c, 'def _on_media_status_changed')
if i_ms >= 0:
    lines = c.split('\n')
    # Find method end
    end = i_ms + 1
    while end < len(lines):
        if lines[end].startswith('    def ') and 'media_status' not in lines[end]:
            break
        end += 1
    # Replace with simplified comment
    new_method = ['    def _on_media_status_changed(self, status) -> None:',
                  '        """VLC 不需要此方法，状态由 _poll_vlc_state 处理"""',
                  '        pass']
    lines = lreplace(lines, i_ms, end, new_method)
    c = '\n'.join(lines)
    print('  [21] _on_media_status_changed')
verify(c, '21')

# ── 22. _on_player_error: 简化 ──
i_err = find_line(c, 'def _on_player_error')
if i_err >= 0:
    lines = c.split('\n')
    end = i_err + 1
    while end < len(lines):
        if lines[end].startswith('    def ') and '_on_player_error' not in lines[end]:
            break
        end += 1
    new_method = ['    def _on_player_error(self, msg: str) -> None:',
                  '        logger.error("播放错误: %s", msg)']
    lines = lreplace(lines, i_err, end, new_method)
    c = '\n'.join(lines)
    print('  [22] _on_player_error')
verify(c, '22')

# ── 23. _add_to_history: 不置顶 ──
i_addh = find_line(c, 'def _add_to_history(self, title: str')
i_addh_end = find_line(c, '    def _refresh_history_list', i_addh)
if i_addh >= 0 and i_addh_end >= 0:
    lines = c.split('\n')
    new_method = [
        '    def _add_to_history(self, title: str, file_path: str, duration: Optional[int] = None) -> None:',
        '        """添加视频到历史记录（去重，不改变原有顺序，只更新元数据）"""',
        '        file_path = os.path.abspath(file_path)',
        '',
        '        existing_idx = None',
        '        for i, h in enumerate(self._video_history):',
        '            if h.get("path") == file_path:',
        '                existing_idx = i',
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
    lines = lreplace(lines, i_addh, i_addh_end, new_method)
    c = '\n'.join(lines)
    print('  [23] _add_to_history no-reorder')
verify(c, '23')

# ── 24. _toggle_subtitle_display: subtitle_panel 控制 ──
i_toggle = find_line(c, 'def _toggle_subtitle_display(self)')
if i_toggle >= 0:
    lines = c.split('\n')
    end = i_toggle + 1
    while end < len(lines):
        if lines[end].startswith('    def ') and '_toggle_subtitle' not in lines[end]:
            break
        end += 1
    new_method = [
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
    lines = lreplace(lines, i_toggle, end, new_method)
    c = '\n'.join(lines)
    print('  [24] _toggle_subtitle_display')
verify(c, '24')

# ── 25. 新增辅助方法（插在 _toggle_subtitle_display 之前）─
i_toggle2 = find_line(c, 'def _toggle_subtitle_display(self)')
lines = c.split('\n')
new_helpers = [
    '    # ── 进度条点击定位 ─────────────────────────────────────────────────',
    '    def _on_slider_click(self, event, slider):',
    '        """进度条任意位置点击时精准跳转"""',
    '        if slider.maximum() == 0:',
    '            return',
    '        val = slider.minimum() + (slider.maximum() - slider.minimum()) * event.position().x() / slider.width()',
    '        pos = int(val)',
    '        slider.setValue(pos)',
    '        self._seek_position(pos)',
    '',
    '    # ── 音量控制 ─────────────────────────────────────────────────────────',
    '    def _adjust_volume_up(self) -> None:',
    '        if self._vlc_player:',
    '            vol = min(100, self._vlc_player.audio_get_volume() + 10)',
    '            self._vlc_player.audio_set_volume(vol)',
    '            self.volume_slider.setValue(vol)',
    '',
    '    def _adjust_volume_down(self) -> None:',
    '        if self._vlc_player:',
    '            vol = max(0, self._vlc_player.audio_get_volume() - 10)',
    '            self._vlc_player.audio_set_volume(vol)',
    '            self.volume_slider.setValue(vol)',
    '',
    '    def _on_volume_slider_changed(self, value: int) -> None:',
    '        if self._vlc_player:',
    '            self._vlc_player.audio_set_volume(value)',
    '',
    '',
]
# Find actual line
for i in range(len(lines)):
    if 'def _toggle_subtitle_display(self)' in lines[i]:
        lines.insert(i, '\n'.join(new_helpers))
        break
c = '\n'.join(lines)
print('  [25] helper methods')
verify(c, '25')

# ── 26. closeEvent: 释放 VLC ──
i_close = find_line(c, 'def closeEvent(self, event)')
if i_close >= 0:
    lines = c.split('\n')
    for i in range(i_close, i_close+5):
        if 'self.media_player.stop()' in lines[i]:
            lines[i] = '            if hasattr(self, "_vlc_player") and self._vlc_player:\n                self._vlc_player.stop()\n            if hasattr(self, "_vlc_instance") and self._vlc_instance:\n                self._vlc_instance.release()'
            break
    c = '\n'.join(lines)
    print('  [26] closeEvent VLC')
verify(c, '26')

# Final
if verify(c, 'FINAL'):
    save(c)
    print('All done.')
else:
    sys.exit(1)
