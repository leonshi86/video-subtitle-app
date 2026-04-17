#!/usr/bin/env python3
"""行级全量修复脚本 - 单次遍历，无多行匹配"""
import ast

PATH = 'gui/main_window.py'

def load(): return open(PATH, encoding='utf-8').read().splitlines()
def save(lines): open(PATH, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
def verify(lines):
    try: ast.parse('\n'.join(lines)); return True
    except SyntaxError as e: print(f'  SYNTAX ERROR line {e.lineno}: {e.msg}'); return False

lines = load()
print(f'File: {len(lines)} lines')

def repl(old, new, tag=''):
    """行内替换"""
    for i, l in enumerate(lines):
        if old in l:
            lines[i] = l.replace(old, new)

# ═══════════════════════════════════════════════════════════════
# 1. imports
# ═══════════════════════════════════════════════════════════════
repl('from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput', 'import vlc  # VLC 播放器', 'import_vlc')
repl('from PySide6.QtMultimediaWidgets import QVideoWidget', '# QVideoWidget removed', 'import_videowidget')
repl('self.video_widget = QVideoWidget()', 'self.video_widget = QWidget()', 'video_widget')
print('  [1] imports OK')

# ═══════════════════════════════════════════════════════════════
# 2. 单行 media_player 替换（不碰 setSource）
# ═══════════════════════════════════════════════════════════════
single = [
    ('self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState', 'self._vlc_player.get_state() == vlc.State.Playing'),
    ('self.media_player.playbackState()', 'self._vlc_player.get_state()'),
    ('QMediaPlayer.PlaybackState.PlayingState', 'vlc.State.Playing'),
    ('QMediaPlayer.PlaybackState.PausedState', 'vlc.State.Paused'),
    ('QMediaPlayer.PlaybackState.StoppedState', 'vlc.State.Stopped'),
    ('QMediaPlayer.MediaStatus.LoadedMedia', 'vlc.State.Playing'),
    ('QMediaPlayer.MediaStatus.BufferedMedia', 'vlc.State.Playing'),
    ('self.media_player.source().isValid()', 'self._vlc_player.get_media() is not None'),
    ('self.media_player.source().toString()', '(self._current_video_path or "")'),
    ('self.media_player.source().toLocalFile()', '(self._current_video_path or "")'),
    ('self.media_player.play()', 'self._vlc_player.play()'),
    ('self.media_player.pause()', 'self._vlc_player.pause()'),
    ('self.media_player.stop()', 'self._vlc_player.stop()'),
    ('self.media_player.setPosition(position)', 'self._vlc_player.set_time(position)'),
    ('self.media_player.duration()', 'self._vlc_player.get_length()'),
]
for old, new in single:
    for i, l in enumerate(lines):
        if old in l:
            lines[i] = l.replace(old, new)
print(f'  [2] media_player replacements OK')

# ═══════════════════════════════════════════════════════════════
# 3. setSource 替换（逐行处理）
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if 'self.media_player.setSource(' in l:
        lines[i] = l.replace('self.media_player.setSource(media_source)', 'self._vlc_player.set_media(media)')
        # 找对应的 media_source 定义行
        for j in range(i-1, max(-1, i-5), -1):
            if 'media_source = QUrl.fromLocalFile(file_path)' in lines[j]:
                lines[j] = '        media = self._vlc_instance.media_new(file_path)'
                break
            elif 'media = self._vlc_instance.media_new(file_path)' in lines[j]:
                break
        # logger 行
        if i-1 >= 0 and 'logger.info("媒体源 URI:' in lines[i-1]:
            lines[i-1] = '        logger.info("VLC 媒体源: %s", file_path)'
        print(f'  [3] setSource at line {i+1}')

# ═══════════════════════════════════════════════════════════════
# 4. 移除信号连接块
# ═══════════════════════════════════════════════════════════════
# 找 # 播放器状态变化 这一行（信号块开始）
signal_start = -1
signal_end = -1
for i, l in enumerate(lines):
    if l.strip() == '# 播放器状态变化':
        signal_start = i
    if signal_start >= 0 and signal_end < 0:
        if 'self.media_player.mediaStatusChanged.connect' in l:
            signal_end = i + 1  # 包含这一行
            break

if signal_start >= 0 and signal_end >= 0:
    # 替换为单行注释
    lines = lines[:signal_start] + ['        # VLC 状态通过 _poll_timer 轮询'] + lines[signal_end:]
    print(f'  [4] signals removed lines {signal_start+1}-{signal_end}')
else:
    print('  [4] signals NOT FOUND')

# ═══════════════════════════════════════════════════════════════
# 5. 替换 _setup_media_player（行级重写）
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if 'def _setup_media_player(self)' in l:
        # 找方法结束：下一个 # ── 信号连接
        end = i + 1
        while end < len(lines):
            if lines[end].startswith('    # ──') and ('信号' in lines[end] or 'connect' in lines[end].lower()):
                break
            end += 1
        new_body = [
            '        """初始化 VLC 媒体播放器（全局禁用内嵌字幕）"""',
            '        self._vlc_instance = vlc.Instance(',
            '            "--network-caching=1000",',
            '            "--file-caching=500",',
            '            "--avcodec-hw=any",',
            '            "--no-spu",',
            '            "--no-sub-autodetect-file",',
            '            "--verbose=0",',
            '        )',
            '        self._vlc_player = self._vlc_instance.media_player_new()',
            '        if sys.platform == "win32":',
            '            self._vlc_player.set_hwnd(self.video_widget.winId())',
            '        elif sys.platform == "darwin":',
            '            self._vlc_player.set_nsobject(int(self.video_widget.winId()))',
            '        self._vlc_player.audio_set_volume(80)',
            '        ',
            '        self._poll_timer = QTimer(self)',
            '        self._poll_timer.setInterval(80)',
            '        self._poll_timer.timeout.connect(self._poll_vlc_state)',
            '        self._poll_timer.start()',
            '        self._vlc_prev_state = None',
            '        self._vlc_prev_media = None',
            '',
        ]
        lines = lines[:i] + new_body + lines[end:]
        print(f'  [5] setup_media at line {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 6. 状态变量初始化
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if 'self._auto_play_pending: bool = False' in l:
        lines[i] = l + '\n        self._sync_last_pos_ms: int = -1'
        print(f'  [6] sync_init at line {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 7. _on_state_changed → _on_vlc_state_changed（行级）
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if '@Slot(QMediaPlayer.PlaybackState)' in l and '_on_state_changed' in lines[i+1]:
        end = i + 1
        while end < len(lines):
            if lines[end].startswith('    def ') and '_on_state' not in lines[end]:
                break
            end += 1
        new_method = [
            '    def _on_vlc_state_changed(self, new_state: vlc.State) -> None:',
            '        if new_state == vlc.State.Playing:',
            '            self.play_btn.setText("\u23f8 \u505c\u6b62")',
            '        elif new_state == vlc.State.Paused:',
            '            self.play_btn.setText("\u25b6 \u64ad\u653e")',
            '        elif new_state in (vlc.State.Stopped, vlc.State.Ended):',
            '            self.play_btn.setText("\u25b6 \u64ad\u653e")',
            '            self.current_subtitle_label.setVisible(False)',
            '            self._highlight_subtitle_row(-1)',
            '        self._refresh_history_list()',
            '',
        ]
        lines = lines[:i] + new_method + lines[end:]
        print(f'  [7] state_changed at line {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 8. _on_media_status_changed 简化
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if '@Slot("QMediaPlayer::MediaStatus")' in l:
        end = i + 1
        while end < len(lines):
            if lines[end].startswith('    def ') and '_on_media' not in lines[end]:
                break
            end += 1
        lines = lines[:i] + ['    def _on_media_status_changed(self, status) -> None:', '        pass', ''] + lines[end:]
        print(f'  [8] media_status at line {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 9. _on_player_error 简化
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if '@Slot(QMediaPlayer.Error, str)' in l:
        end = i + 1
        while end < len(lines):
            if lines[end].startswith('    # ──') and '\u5bfc\u51fa' in lines[end]:
                break
            end += 1
        lines = lines[:i] + ['    def _on_player_error(self, msg: str = "") -> None:', '        logger.error("播放器错误: %s", msg)', ''] + lines[end:]
        print(f'  [9] player_error at line {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 10. 移除 @Slot 装饰器
# ═══════════════════════════════════════════════════════════════
slots = ['@Slot()', '@Slot(int)', '@Slot(float)', '@Slot(str)', '@Slot(object)', '@Slot(list)']
new_lines = []
skip_next = False
for l in lines:
    stripped = l.strip()
    if skip_next:
        skip_next = False
        continue
    if stripped in slots:
        skip_next = True
        continue
    new_lines.append(l)
lines = new_lines
print('  [10] slots removed')

# ═══════════════════════════════════════════════════════════════
# 11. closeEvent
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if l.strip() == 'self._vlc_player.stop()' and i+2 < len(lines) and '\u505c\u6b62\u540e\u53f0\u7ebf\u7a0b' in lines[i+2]:
        lines[i] = '        if hasattr(self, "_vlc_player") and self._vlc_player:'
        lines.insert(i+1, '            self._vlc_player.stop()')
        lines.insert(i+2, '        if hasattr(self, "_vlc_instance") and self._vlc_instance:')
        lines.insert(i+3, '            self._vlc_instance.release()')
        print(f'  [11] closeEvent at line {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 12. _stop_playback
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if 'def _stop_playback(self)' in l:
        end = i + 1
        while end < len(lines):
            if lines[end].startswith('    def ') and '_stop' not in lines[end]:
                break
            end += 1
        new_method = [
            '    def _stop_playback(self) -> None:',
            '        """\u505c\u6b62\u64ad\u653e"""',
            '        self._vlc_player.stop()',
            '        self.play_btn.setText("\u25b6 \u64ad\u653e")',
            '        self.position_slider.setValue(0)',
            '        self._sync_last_pos_ms = -1',
            '        self.volume_slider.setEnabled(False)',
            '        self.volume_up_btn.setEnabled(False)',
            '        self.volume_down_btn.setEnabled(False)',
            '        self.subtitle_toggle_btn.setEnabled(False)',
            '',
        ]
        lines = lines[:i] + new_method + lines[end:]
        print(f'  [12] stop_playback at line {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 13. _load_video 启用控件
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if 'self.position_slider.setEnabled(True)' in l:
        # 检查下面一行是不是 title 或 time_label
        if i+1 < len(lines) and ('title = os.path.splitext' in lines[i+1] or 'time_label' in lines[i+1]):
            insert_lines = [
                '        self.volume_slider.setEnabled(True)',
                '        self.volume_up_btn.setEnabled(True)',
                '        self.volume_down_btn.setEnabled(True)',
                '        self.subtitle_toggle_btn.setEnabled(True)',
            ]
            for k, ins in enumerate(insert_lines):
                lines.insert(i+1+k, ins)
            print(f'  [13] enable_controls at line {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 14. _add_to_history 不置顶
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if 'self._video_history = [entry] + remaining' in l:
        lines[i] = '        # \u4e0d\u7f6e\u9876\uff1a\u539f\u5730\u66f4\u65b0\u6216\u8ffd\u52a0\u672b\u5c3e'
        print(f'  [14] no_reorder at line {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 15. 新增方法（插入 _on_vlc_state_changed 之前）
# ═══════════════════════════════════════════════════════════════
new_methods = [
    '    def _poll_vlc_state(self) -> None:',
    '        """\u8f6e\u8be2 VLC \u64ad\u653e\u5668\u72b6\u6001/\u8fdb\u5ea6"""',
    '        cur_state = self._vlc_player.get_state()',
    '        if cur_state != self._vlc_prev_state:',
    '            self._on_vlc_state_changed(cur_state)',
    '            self._vlc_prev_state = cur_state',
    '        cur_media = self._vlc_player.get_media()',
    '        if cur_media is not self._vlc_prev_media:',
    '            if cur_media is not None:',
    '                self._on_duration_changed(self._vlc_player.get_length())',
    '                self._hide_loading()',
    '                display_title = self._get_display_title()',
    '                self.status_label.setText(f"\u5df2\u52a0\u8f7d: {display_title}")',
    '                if self._auto_play_pending:',
    '                    self._auto_play_pending = False',
    '                    self._toggle_playback()',
    '            self._vlc_prev_media = cur_media',
    '        if cur_state == vlc.State.Playing:',
    '            self._on_position_changed(self._vlc_player.get_time())',
    '',
    '    def _get_display_title(self) -> str:',
    '        if hasattr(self, "_download_title") and self._download_title:',
    '            return self._download_title',
    '        if self._current_video_path:',
    '            name = os.path.splitext(os.path.basename(self._current_video_path))[0]',
    '            if name.lower() not in ("stream", "\u89c6\u9891"):',
    '                return name',
    '        return "\u89c6\u9891"',
    '',
    '    # \u2500\u2500 \u8fdb\u5ea6\u6761\u70b9\u51fb\u5b9a\u4f4d \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500',
    '    def _on_slider_click(self, event, slider):',
    '        if slider.maximum() == 0: return',
    '        val = slider.minimum() + (slider.maximum() - slider.minimum()) * event.position().x() / slider.width()',
    '        slider.setValue(int(val))',
    '        self._seek_position(int(val))',
    '',
    '    # \u2500\u2500 \u97f3\u91cf\u63a7\u5236 \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500',
    '    def _adjust_volume_up(self) -> None:',
    '        if hasattr(self, "_vlc_player") and self._vlc_player:',
    '            vol = min(100, self._vlc_player.audio_get_volume() + 10)',
    '            self._vlc_player.audio_set_volume(vol)',
    '            self.volume_slider.setValue(vol)',
    '',
    '    def _adjust_volume_down(self) -> None:',
    '        if hasattr(self, "_vlc_player") and self._vlc_player:',
    '            vol = max(0, self._vlc_player.audio_get_volume() - 10)',
    '            self._vlc_player.audio_set_volume(vol)',
    '            self.volume_slider.setValue(vol)',
    '',
    '    def _on_volume_slider_changed(self, value: int) -> None:',
    '        if hasattr(self, "_vlc_player") and self._vlc_player:',
    '            self._vlc_player.audio_set_volume(value)',
    '',
    '    # \u2500\u2500 \u5b57\u5e55\u5f00\u5173 \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500',
    '    def _toggle_subtitle_display(self) -> None:',
    '        self._subtitle_panel_visible = not self._subtitle_panel_visible',
    '        self.subtitle_panel.setVisible(self._subtitle_panel_visible)',
    '        if self._subtitle_panel_visible:',
    '            self.subtitle_toggle_btn.setText("\u5173\u5b57\u5e55")',
    '            self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #EF5350; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #E53935; }")',
    '        else:',
    '            self.subtitle_toggle_btn.setText("\u5f00\u5b57\u5e55")',
    '            self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #66BB6A; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #43A047; }")',
    '',
]
for i, l in enumerate(lines):
    if '    def _on_vlc_state_changed(self' in l:
        lines = lines[:i] + new_methods + lines[i:]
        print(f'  [15] new_methods at line {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 16. UI 控件
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if '        subtitle_panel = QWidget()' in l:
        lines[i] = '        self.subtitle_panel = QWidget()'
    elif 'subtitle_layout = QVBoxLayout(subtitle_panel)' in l:
        lines[i] = 'subtitle_layout = QVBoxLayout(self.subtitle_panel)'
    elif 'right_layout.addWidget(subtitle_panel)' in l:
        lines[i] = 'right_layout.addWidget(self.subtitle_panel)'
    elif '        history_panel = QWidget()' in l and i+1 < len(lines) and 'history_panel.setStyleSheet' in lines[i+1]:
        lines.insert(i+1, '        history_panel.setMinimumWidth(180)')
    elif 'self.position_slider.setFixedHeight(20)' in l and i+1 < len(lines) and 'control_layout.addWidget(self.position_slider' in lines[i+1]:
        lines.insert(i+1, '        self.position_slider.setPageStep(0)')
        lines.insert(i+2, '        self.position_slider.mousePressEvent = lambda e: self._on_slider_click(e, self.position_slider)')
    elif 'content_splitter.setStyleSheet("QSplitter::handle { width: 1px; background: #21262D; }")' in l:
        lines[i] = 'content_splitter.setStyleSheet("QSplitter::handle { width: 4px; background: #90CAF9; border-radius: 2px; }")\n        content_splitter.setCollapsible(0, False)'
print('  [16] UI controls OK')

# ═══════════════════════════════════════════════════════════════
# 17. 音量和字幕按钮
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if 'self.time_label.setStyleSheet("color: #8B949E; font-size: 12px;")' in l and i+1 < len(lines) and 'control_layout.addWidget(self.time_label)' in lines[i+1]:
        vol_code = [
            '        self.time_label.setStyleSheet("color: #5D7A9C; font-size: 12px;")',
            '        control_layout.addWidget(self.time_label)',
            '        # \u97f3\u91cf\u63a7\u5236',
            '        volume_layout = QHBoxLayout()',
            '        volume_layout.setSpacing(4)',
            '        self.volume_down_btn = QPushButton("-")',
            '        self.volume_down_btn.setFixedSize(26, 26)',
            '        self.volume_down_btn.setStyleSheet("QPushButton { background-color: #90CAF9; border: none; border-radius: 4px; color: white; font-size: 14px; font-weight: bold; } QPushButton:hover { background-color: #42A5F5; } QPushButton:disabled { background-color: #E3F2FD; color: #90CAF9; }")',
            '        self.volume_down_btn.clicked.connect(self._adjust_volume_down)',
            '        self.volume_down_btn.setEnabled(False)',
            '        self.volume_slider = QSlider(Qt.Orientation.Horizontal)',
            '        self.volume_slider.setRange(0, 100)',
            '        self.volume_slider.setValue(80)',
            '        self.volume_slider.setFixedWidth(80)',
            '        self.volume_slider.setEnabled(False)',
            '        self.volume_slider.setStyleSheet("QSlider::groove:horizontal { height: 4px; background: #BBDEFB; border-radius: 2px; } QSlider::handle:horizontal { width: 10px; background: #42A5F5; border-radius: 5px; margin: -3px 0; } QSlider::sub-page:horizontal { background: #42A5F5; border-radius: 2px; }")',
            '        self.volume_slider.valueChanged.connect(self._on_volume_slider_changed)',
            '        self.volume_up_btn = QPushButton("+")',
            '        self.volume_up_btn.setFixedSize(26, 26)',
            '        self.volume_up_btn.setStyleSheet("QPushButton { background-color: #90CAF9; border: none; border-radius: 4px; color: white; font-size: 14px; font-weight: bold; } QPushButton:hover { background-color: #42A5F5; } QPushButton:disabled { background-color: #E3F2FD; color: #90CAF9; }")',
            '        self.volume_up_btn.clicked.connect(self._adjust_volume_up)',
            '        self.volume_up_btn.setEnabled(False)',
            '        volume_layout.addWidget(self.volume_down_btn)',
            '        volume_layout.addWidget(self.volume_slider)',
            '        volume_layout.addWidget(self.volume_up_btn)',
            '        control_layout.addLayout(volume_layout)',
            '        self.subtitle_toggle_btn = QPushButton("\u5173\u5b57\u5e55")',
            '        self.subtitle_toggle_btn.setFixedHeight(32)',
            '        self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #EF5350; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #E53935; } QPushButton:disabled { background-color: #E8F5E9; color: #A5D6A7; }")',
            '        self.subtitle_toggle_btn.clicked.connect(self._toggle_subtitle_display)',
            '        self.subtitle_toggle_btn.setEnabled(False)',
            '        self._subtitle_panel_visible = True',
            '        control_layout.addWidget(self.subtitle_toggle_btn)',
        ]
        lines = lines[:i] + vol_code + lines[i+2:]
        print(f'  [17] volume_buttons at line {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 18. 浅蓝主题颜色
# ═══════════════════════════════════════════════════════════════
theme = [
    ('#0D1117', '#FFFFFF'),
    ('#161B22', '#FFFFFF'),
    ('#1C2128', '#FFFFFF'),
    ('#21262D', '#FFFFFF'),
    ('#30363D', '#BBDEFB'),
    ('color: #E6EDF3', 'color: #1E3A5F'),
    ('color: #8B949E', 'color: #5D7A9C'),
    ('color: #6E7681', 'color: #5D7A9C'),
    ('background: #30363D', 'background: #E3F2FD'),
    ('background: #21262D', 'background: #E3F2FD'),
    ('border-bottom: 1px solid #21262D', 'border-bottom: 1px solid #BBDEFB'),
    ('background-color: #238636', 'background-color: #4CAF50'),
    ('border: 1px solid #30363D', 'border: 1px solid #BBDEFB'),
    ('background-color: #21262D; color: #E6EDF3', 'background-color: #90CAF9; color: #FFFFFF'),
]
for old, new in theme:
    for i, l in enumerate(lines):
        if old in l:
            lines[i] = l.replace(old, new)
# subtitle_panel 样式
for i, l in enumerate(lines):
    if 'self.subtitle_panel.setStyleSheet' in l:
        lines[i] = l.replace('#161B22', '#FFFFFF').replace('#21262D', '#BBDEFB')
print('  [18] theme colors OK')

# ═══════════════════════════════════════════════════════════════
# 19. 窗口渐变背景
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if 'central_widget = QWidget()' in l and i+1 < len(lines) and 'self.setCentralWidget(central_widget)' in lines[i+1]:
        lines.insert(i+4, '        # \u6d45\u84dd\u6e10\u53d8\u80cc\u666f')
        lines.insert(i+5, '        self.setAutoFillBackground(True)')
        lines.insert(i+6, '        p = self.palette()')
        lines.insert(i+7, '        p.setBrush(self.backgroundRole(), QColor(245, 249, 255))')
        lines.insert(i+8, '        self.setPalette(p)')
        print(f'  [19] gradient at line {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 最终验证
# ═══════════════════════════════════════════════════════════════
if verify(lines):
    save(lines)
    print(f'\nAll 19 stages complete! Final: {len(lines)} lines')
    import re
    src = '\n'.join(lines)
    mp = re.findall(r'self\.media_player(?![\w_])', src)
    qmp = re.findall(r'QMediaPlayer\.', src)
    dark = re.findall(r'#0D1117|#161B22|#21262D', src)
    print(f'  media_player refs: {len(mp)}')
    print(f'  QMediaPlayer refs: {len(qmp)}')
    print(f'  dark color refs: {len(dark)}')
else:
    print('\nFAILED')
