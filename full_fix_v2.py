#!/usr/bin/env python3
"""
精确完整修复脚本 - 分阶段执行
每个阶段后验证语法
"""
import ast, re

PATH = 'gui/main_window.py'

def load(): return open(PATH, encoding='utf-8').read()
def save(c): open(PATH, 'w', encoding='utf-8').write(c)
def verify(c):
    try: ast.parse(c); return True
    except SyntaxError as e:
        print(f'SYNTAX ERROR line {e.lineno}: {e.msg}')
        return False

print('=== 阶段 1: imports ===')
c = load()
c = c.replace('from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput', 'import vlc  # VLC 播放器')
c = c.replace('from PySide6.QtMultimediaWidgets import QVideoWidget', '# QVideoWidget 已移除')
c = c.replace('        self.video_widget = QVideoWidget()', '        self.video_widget = QWidget()')
if verify(c): save(c); print('OK')

print('\n=== 阶段 2: _setup_media_player ===')
c = load()
# 找到方法的开始和结束
lines = c.split('\n')
start = end = -1
for i, l in enumerate(lines):
    if '    def _setup_media_player(self)' in l:
        start = i
    if start >= 0 and end < 0 and i > start and l.startswith('    # ── ') and '信号连接' in l:
        end = i
        break

if start >= 0 and end >= 0:
    new_method = [
        '    # ── 媒体播放器初始化 ───────────────────────────────────────────────────',
        '    def _setup_media_player(self) -> None:',
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
        '        # 轮询定时器',
        '        self._poll_timer = QTimer(self)',
        '        self._poll_timer.setInterval(80)',
        '        self._poll_timer.timeout.connect(self._poll_vlc_state)',
        '        self._poll_timer.start()',
        '        self._vlc_prev_state = None',
        '        self._vlc_prev_media = None',
        '',
    ]
    lines = lines[:start] + new_method + lines[end:]
    c = '\n'.join(lines)
    if verify(c): save(c); print('OK')

print('\n=== 阶段 3: 移除信号连接 ===')
c = load()
lines = c.split('\n')
start = end = -1
for i, l in enumerate(lines):
    if '        # 播放器状态变化' in l:
        start = i
    if start >= 0 and end < 0 and '# 导出' in l:
        end = i
        break

if start >= 0 and end >= 0:
    lines = lines[:start] + ['        # VLC 状态通过 _poll_timer 轮询，不需要 Qt 信号连接'] + lines[end:]
    c = '\n'.join(lines)
    if verify(c): save(c); print('OK')

print('\n=== 阶段 4: 添加状态变量 ===')
c = load()
if 'self._sync_last_pos_ms' not in c:
    c = c.replace(
        '        self._auto_play_pending: bool = False',
        '        self._auto_play_pending: bool = False\n        self._sync_last_pos_ms: int = -1'
    )
    if verify(c): save(c); print('OK')

print('\n=== 阶段 5: 替换所有 media_player 引用 ===')
c = load()
# 按顺序替换，先长后短
replacements = [
    ('self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState', 'self._vlc_player.get_state() == vlc.State.Playing'),
    ('self.media_player.playbackState() == QMediaPlayer.PlaybackState.PausedState', 'self._vlc_player.get_state() == vlc.State.Paused'),
    ('self.media_player.playbackState() == QMediaPlayer.PlaybackState.StoppedState', 'self._vlc_player.get_state() == vlc.State.Stopped'),
    ('QMediaPlayer.PlaybackState.PlayingState', 'vlc.State.Playing'),
    ('QMediaPlayer.PlaybackState.PausedState', 'vlc.State.Paused'),
    ('QMediaPlayer.PlaybackState.StoppedState', 'vlc.State.Stopped'),
    ('QMediaPlayer.MediaStatus.LoadedMedia', 'vlc.State.Playing'),
    ('QMediaPlayer.MediaStatus.BufferedMedia', 'vlc.State.Playing'),
    ('self.media_player.playbackState()', 'self._vlc_player.get_state()'),
    ('self.media_player.source().isValid()', 'self._vlc_player.get_media() is not None'),
    ('self.media_player.source().toString()', '(self._current_video_path or "")'),
    ('self.media_player.source().toLocalFile()', '(self._current_video_path or "")'),
    ('self.media_player.play()', 'self._vlc_player.play()'),
    ('self.media_player.pause()', 'self._vlc_player.pause()'),
    ('self.media_player.stop()', 'self._vlc_player.stop()'),
    ('self.media_player.setPosition(position)', 'self._vlc_player.set_time(position)'),
    ('self.media_player.duration()', 'self._vlc_player.get_length()'),
]
for old, new in replacements:
    c = c.replace(old, new)
if verify(c): save(c); print('OK')

print('\n=== 阶段 6: 替换 setSource ===')
c = load()
c = c.replace(
    '        media_source = QUrl.fromLocalFile(file_path)\n        logger.info("媒体源 URI: %s", media_source.toString())\n        self._vlc_player.setSource(media_source)',
    '        media = self._vlc_instance.media_new(file_path)\n        self._vlc_player.set_media(media)\n        logger.info("VLC 媒体源: %s", file_path)'
)
c = c.replace('self._vlc_player.setSource(media_source)', 'self._vlc_player.set_media(self._vlc_instance.media_new(file_path))')
if verify(c): save(c); print('OK')

print('\n=== 阶段 7: 替换 _on_state_changed ===')
c = load()
lines = c.split('\n')
start = end = -1
for i, l in enumerate(lines):
    if '@Slot(QMediaPlayer.PlaybackState)' in l and i+1 < len(lines) and '_on_state_changed' in lines[i+1]:
        start = i
    if start >= 0 and end < 0 and i > start and l.startswith('    def ') and '_on_state' not in l:
        end = i
        break

if start >= 0 and end >= 0:
    new_method = [
        '    def _on_vlc_state_changed(self, new_state: vlc.State) -> None:',
        '        """播放状态变化"""',
        '        if new_state == vlc.State.Playing:',
        '            self.play_btn.setText("⏸ 暂停")',
        '        elif new_state == vlc.State.Paused:',
        '            self.play_btn.setText("▶ 播放")',
        '        elif new_state in (vlc.State.Stopped, vlc.State.Ended):',
        '            self.play_btn.setText("▶ 播放")',
        '            self.current_subtitle_label.setVisible(False)',
        '            self._highlight_subtitle_row(-1)',
        '        self._refresh_history_list()',
        '',
    ]
    lines = lines[:start] + new_method + lines[end:]
    c = '\n'.join(lines)
    if verify(c): save(c); print('OK')

print('\n=== 阶段 8: 替换 _on_media_status_changed ===')
c = load()
lines = c.split('\n')
start = end = -1
for i, l in enumerate(lines):
    if '@Slot("QMediaPlayer::MediaStatus")' in l:
        start = i
    if start >= 0 and end < 0 and i > start and l.startswith('    def ') and '_on_media' not in l:
        end = i
        break

if start >= 0 and end >= 0:
    lines = lines[:start] + [
        '    def _on_media_status_changed(self, status) -> None:',
        '        """VLC 不需要，状态由 _poll_vlc_state 处理"""',
        '        pass',
        ''
    ] + lines[end:]
    c = '\n'.join(lines)
    if verify(c): save(c); print('OK')

print('\n=== 阶段 9: 替换 _on_player_error ===')
c = load()
lines = c.split('\n')
start = end = -1
for i, l in enumerate(lines):
    if '@Slot(QMediaPlayer.Error, str)' in l:
        start = i
    if start >= 0 and end < 0 and i > start and l.startswith('    def ') and '_on_player' not in l:
        end = i
        break

if start >= 0 and end >= 0:
    lines = lines[:start] + [
        '    def _on_player_error(self, msg: str = "") -> None:',
        '        """播放器错误"""',
        '        logger.error("播放器错误: %s", msg)',
        ''
    ] + lines[end:]
    c = '\n'.join(lines)
    if verify(c): save(c); print('OK')

print('\n=== 阶段 10: 添加 _poll_vlc_state 和 _get_display_title ===')
c = load()
new_methods = '''
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

'''
if '_poll_vlc_state' not in c:
    lines = c.split('\n')
    for i, l in enumerate(lines):
        if '    def _on_vlc_state_changed' in l:
            lines.insert(i, new_methods)
            break
    c = '\n'.join(lines)
    if verify(c): save(c); print('OK')

print('\n=== 阶段 11: 添加辅助方法 ===')
helpers = '''
    # ── 进度条点击定位 ─────────────────────────────────────────────────
    def _on_slider_click(self, event, slider):
        if slider.maximum() == 0: return
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
        self._subtitle_panel_visible = not self._subtitle_panel_visible
        self.subtitle_panel.setVisible(self._subtitle_panel_visible)
        if self._subtitle_panel_visible:
            self.subtitle_toggle_btn.setText("关字幕")
            self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #EF5350; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #E53935; }")
        else:
            self.subtitle_toggle_btn.setText("开字幕")
            self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #66BB6A; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #43A047; }")

'''
c = load()
if '_on_slider_click' not in c:
    lines = c.split('\n')
    for i, l in enumerate(lines):
        if '    def _get_display_title' in l:
            lines.insert(i, helpers)
            break
    c = '\n'.join(lines)
    if verify(c): save(c); print('OK')

print('\n=== 阶段 12: UI 控件 ===')
c = load()
# 进度条点击
c = c.replace(
    '        self.position_slider.setFixedHeight(20)\n        control_layout.addWidget(self.position_slider, stretch=1)',
    '        self.position_slider.setFixedHeight(20)\n        self.position_slider.setPageStep(0)\n        self.position_slider.mousePressEvent = lambda e: self._on_slider_click(e, self.position_slider)\n        control_layout.addWidget(self.position_slider, stretch=1)'
)
# subtitle_panel
c = c.replace('        subtitle_panel = QWidget()', '        self.subtitle_panel = QWidget()')
c = c.replace('subtitle_layout = QVBoxLayout(subtitle_panel)', 'subtitle_layout = QVBoxLayout(self.subtitle_panel)')
c = c.replace('right_layout.addWidget(subtitle_panel)', 'right_layout.addWidget(self.subtitle_panel)')
# history_panel
c = c.replace('        history_panel = QWidget()\n        history_panel.setStyleSheet', '        history_panel = QWidget()\n        history_panel.setMinimumWidth(180)\n        history_panel.setStyleSheet')
if verify(c): save(c); print('OK')

print('\n=== 阶段 13: 音量和字幕按钮 ===')
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
        control_layout.addLayout(volume_layout)
        self.subtitle_toggle_btn = QPushButton("关字幕")
        self.subtitle_toggle_btn.setFixedHeight(32)
        self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #EF5350; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #E53935; } QPushButton:disabled { background-color: #E8F5E9; color: #A5D6A7; }")
        self.subtitle_toggle_btn.clicked.connect(self._toggle_subtitle_display)
        self.subtitle_toggle_btn.setEnabled(False)
        self._subtitle_panel_visible = True
        control_layout.addWidget(self.subtitle_toggle_btn)'''

c = load()
if 'volume_slider' not in c:
    c = c.replace(
        '        self.time_label.setStyleSheet("color: #8B949E; font-size: 12px;")\n        control_layout.addWidget(self.time_label)',
        '        self.time_label.setStyleSheet("color: #8B949E; font-size: 12px;")\n        control_layout.addWidget(self.time_label)' + vol_code
    )
    if verify(c): save(c); print('OK')

print('\n=== 阶段 14: 其他修改 ===')
c = load()
# _add_to_history 不置顶
c = c.replace('self._video_history = [entry] + remaining', '# 不置顶：原地更新或追加')
# _stop_playback
c = c.replace(
    '    @Slot()\n    def _stop_playback(self) -> None:\n        """停止播放"""\n        self._vlc_player.stop()\n        self.play_btn.setText("▶ 播放")\n        # 隐藏当前字幕\n        self.current_subtitle_label.setVisible(False)\n        # 停止后恢复转写\n        if self._transcribe_thread and self._transcribe_thread.isRunning():\n            logger.info("停止后恢复转写线程")\n            self._transcribe_worker.resume()',
    '    def _stop_playback(self) -> None:\n        """停止播放"""\n        self._vlc_player.stop()\n        self.play_btn.setText("▶ 播放")\n        self.position_slider.setValue(0)\n        self._sync_last_pos_ms = -1\n        self.volume_slider.setEnabled(False)\n        self.volume_up_btn.setEnabled(False)\n        self.volume_down_btn.setEnabled(False)\n        self.subtitle_toggle_btn.setEnabled(False)'
)
# closeEvent
c = c.replace(
    '        self._vlc_player.stop()\n\n        # 停止后台线程',
    '        if hasattr(self, "_vlc_player") and self._vlc_player:\n            self._vlc_player.stop()\n        if hasattr(self, "_vlc_instance") and self._vlc_instance:\n            self._vlc_instance.release()\n\n        # 停止后台线程'
)
# 启用控件
c = c.replace(
    '        self.position_slider.setEnabled(True)\n\n        title = os.path.splitext',
    '        self.position_slider.setEnabled(True)\n        self.volume_slider.setEnabled(True)\n        self.volume_up_btn.setEnabled(True)\n        self.volume_down_btn.setEnabled(True)\n        self.subtitle_toggle_btn.setEnabled(True)\n\n        title = os.path.splitext'
)
# QSplitter
c = c.replace(
    'content_splitter.setStyleSheet("QSplitter::handle { width: 1px; background: #21262D; }")',
    'content_splitter.setStyleSheet("QSplitter::handle { width: 4px; background: #90CAF9; border-radius: 2px; }")\n        content_splitter.setCollapsible(0, False)'
)
# 移除 @Slot
for slot in ['@Slot()', '@Slot(int)', '@Slot(float)', '@Slot(str)', '@Slot(object)', '@Slot(list)']:
    c = c.replace('    ' + slot + '\n    def', '    def')
if verify(c): save(c); print('OK')

# 最终验证
c = load()
if verify(c):
    # 检查残留
    import re
    mp = re.findall(r'media_player[^_]', c)
    qmp = re.findall(r'QMediaPlayer', c)
    if mp or qmp:
        print(f'\n警告: 仍有残留引用 media_player={len(mp)}, QMediaPlayer={len(qmp)}')
    else:
        print('\n完成! 无 QMediaPlayer 残留')
else:
    print('\n存在语法错误')
