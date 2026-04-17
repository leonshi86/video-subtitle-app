#!/usr/bin/env python3
"""
全量修复脚本：VLC 迁移 + 浅蓝主题 + 所有功能
一次性完成，不依赖 git checkout
"""
import ast, sys

PATH = 'gui/main_window.py'

def load(): return open(PATH, encoding='utf-8').read()
def save(c): open(PATH, 'w', encoding='utf-8').write(c)
def verify(c):
    try:
        ast.parse(c)
        return True
    except SyntaxError as e:
        print(f'  SYNTAX ERROR line {e.lineno}: {e.msg}')
        return False

c = load()

# ═══════════════════════════════════════════════════════════════
# 第一部分：VLC 迁移
# ═══════════════════════════════════════════════════════════════
print('VLC migration...')

# 1. imports
c = c.replace(
    'from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput',
    'import vlc  # VLC 播放器'
)
c = c.replace(
    'from PySide6.QtMultimediaWidgets import QVideoWidget',
    '# QVideoWidget 已移除'
)
print('  [1] imports OK')

# 2. video_widget
c = c.replace(
    '        self.video_widget = QVideoWidget()',
    '        self.video_widget = QWidget()'
)
print('  [2] video_widget OK')

# 3. _setup_media_player
old_setup = '''    # ── 媒体播放器初始化 ───────────────────────────────────────────────────
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
        self.media_player.errorOccurred.connect(self._on_player_error)'''

new_setup = '''    # ── 媒体播放器初始化 ───────────────────────────────────────────────────
    def _setup_media_player(self) -> None:
        """初始化 VLC 媒体播放器（全局禁用内嵌字幕）"""
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

        # 轮询定时器
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(80)
        self._poll_timer.timeout.connect(self._poll_vlc_state)
        self._poll_timer.start()
        self._vlc_prev_state = None
        self._vlc_prev_media = None'''

c = c.replace(old_setup, new_setup)
print('  [3] _setup_media_player OK')

# 4. 状态变量
c = c.replace(
    '        self._auto_play_pending: bool = False',
    '        self._auto_play_pending: bool = False\n        self._sync_last_pos_ms: int = -1'
)
print('  [4] state vars OK')

# 5. 移除信号连接
c = c.replace(
    '''        # 播放器状态变化
        self.media_player.positionChanged.connect(self._on_position_changed)
        self.media_player.durationChanged.connect(self._on_duration_changed)
        self.media_player.playbackStateChanged.connect(self._on_state_changed)
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)''',
    '        # VLC 状态通过 _poll_timer 轮询，不需要 Qt 信号连接'
)
print('  [5] signal connections OK')

# 6. media_player 全量替换（不替换 setSource，改在步骤 7 统一处理 _set_media_source）
replacements = [
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
    # 注意：不替换 setSource，步骤 7 统一处理
]
for old, new in replacements:
    c = c.replace(old, new)
print('  [6] media_player replacements OK')

# 7. _set_media_source（两种情况）
# 情况A：原始 git 版本
c = c.replace(
    '        media_source = QUrl.fromLocalFile(file_path)\n        logger.info("媒体源 URI: %s", media_source.toString())\n        self.media_player.setSource(media_source)',
    '        media = self._vlc_instance.media_new(file_path)\n        self._vlc_player.set_media(media)\n        logger.info("VLC 媒体源: %s", file_path)'
)
# 情况B：步骤 6 产生了中间状态（media_source 作为参数）
c = c.replace(
    'self._vlc_player.set_media(self._vlc_instance.media_new(media_source))',
    'self._vlc_player.set_media(self._vlc_instance.media_new(file_path))'
)
print('  [7] _set_media_source OK')

# 8. _on_state_changed → _on_vlc_state_changed
old_state = '''    @Slot(QMediaPlayer.PlaybackState)
    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        """播放状态变化"""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText("⏸ 暂停")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.play_btn.setText("▶ 播放")
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            self.play_btn.setText("▶ 播放")
            self.current_subtitle_label.setVisible(False)
            self._highlight_subtitle_row(-1)
        self._refresh_history_list()'''

new_state = '''    def _on_vlc_state_changed(self, new_state: vlc.State) -> None:
        """播放状态变化"""
        if new_state == vlc.State.Playing:
            self.play_btn.setText("⏸ 暂停")
        elif new_state == vlc.State.Paused:
            self.play_btn.setText("▶ 播放")
        elif new_state in (vlc.State.Stopped, vlc.State.Ended):
            self.play_btn.setText("▶ 播放")
            self.current_subtitle_label.setVisible(False)
            self._highlight_subtitle_row(-1)
        self._refresh_history_list()'''

c = c.replace(old_state, new_state)
print('  [8] _on_vlc_state_changed OK')

# 9. _on_media_status_changed 简化
old_ms = '''    @Slot("QMediaPlayer::MediaStatus")
    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        """媒体状态变化 → 控制加载提示"""
        logger.info("媒体状态: %s", status)
        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            self._hide_loading()
            title = os.path.splitext(os.path.basename(self._current_video_path or ""))[0]
            self.status_label.setText(f"已加载: {title}")

            # 如果有待播放的请求，自动开始播放
            if self._auto_play_pending:
                self._auto_play_pending = False
                self._toggle_playback()'''

new_ms = '''    def _on_media_status_changed(self, status) -> None:
        """VLC 不需要，状态由 _poll_vlc_state 处理"""
        pass'''

c = c.replace(old_ms, new_ms)
print('  [9] _on_media_status_changed OK')

# 10. _on_player_error 简化
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

c = c.replace(old_err, new_err)
print('  [10] _on_player_error OK')

# 11. 移除 @Slot 装饰器
for slot in ['@Slot()', '@Slot(int)', '@Slot(float)', '@Slot(str)', '@Slot(object)', '@Slot(list)']:
    c = c.replace('    ' + slot + '\n    def', '    def')
print('  [11] @Slot removed OK')

# 12. closeEvent
c = c.replace(
    '        self._vlc_player.stop()\n\n        # 停止后台线程',
    '        if hasattr(self, "_vlc_player") and self._vlc_player:\n            self._vlc_player.stop()\n        if hasattr(self, "_vlc_instance") and self._vlc_instance:\n            self._vlc_instance.release()\n\n        # 停止后台线程'
)
print('  [12] closeEvent OK')

# 13. _stop_playback
c = c.replace(
    '''    def _stop_playback(self) -> None:
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
        self.subtitle_toggle_btn.setEnabled(False)'''
)
print('  [13] _stop_playback OK')

# 14. _load_video 启用控件
c = c.replace(
    '        self.position_slider.setEnabled(True)\n\n        title = os.path.splitext',
    '        self.position_slider.setEnabled(True)\n        self.volume_slider.setEnabled(True)\n        self.volume_up_btn.setEnabled(True)\n        self.volume_down_btn.setEnabled(True)\n        self.subtitle_toggle_btn.setEnabled(True)\n\n        title = os.path.splitext'
)
print('  [14] enable controls OK')

# 15. _add_to_history 不置顶
c = c.replace(
    'self._video_history = [entry] + remaining',
    '# 不置顶：原地更新或追加'
)
print('  [15] add_history no-reorder OK')

# 16. 历史双击中的 QMediaPlayer
c = c.replace(
    'if self.media_player.playbackState() == vlc.State.Playing:',
    'if self._vlc_player.get_state() == vlc.State.Playing:'
)
print('  [16] history double-click OK')

# ═══════════════════════════════════════════════════════════════
# 第二部分：新增方法
# ═══════════════════════════════════════════════════════════════
print('\nAdding methods...')

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

    # ── 进度条点击定位 ─────────────────────────────────────────────────
    def _on_slider_click(self, event, slider):
        if slider.maximum() == 0:
            return
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

if '_poll_vlc_state' not in c:
    lines = c.split('\n')
    for i, l in enumerate(lines):
        if '    def _on_vlc_state_changed(self' in l:
            lines.insert(i, new_methods)
            break
    c = '\n'.join(lines)
    print('  [methods] inserted OK')

# ═══════════════════════════════════════════════════════════════
# 第三部分：UI 控件
# ═══════════════════════════════════════════════════════════════
print('\nAdding UI controls...')

# subtitle_panel self 属性
c = c.replace('        subtitle_panel = QWidget()', '        self.subtitle_panel = QWidget()')
c = c.replace('subtitle_layout = QVBoxLayout(subtitle_panel)', 'subtitle_layout = QVBoxLayout(self.subtitle_panel)')
c = c.replace('right_layout.addWidget(subtitle_panel)', 'right_layout.addWidget(self.subtitle_panel)')
print('  [subtitle_panel] self OK')

# history_panel 最小宽度
c = c.replace(
    '        history_panel = QWidget()\n        history_panel.setStyleSheet',
    '        history_panel = QWidget()\n        history_panel.setMinimumWidth(180)\n        history_panel.setStyleSheet'
)
print('  [history_panel] min width OK')

# 进度条点击
c = c.replace(
    '        self.position_slider.setFixedHeight(20)\n        control_layout.addWidget(self.position_slider, stretch=1)',
    '        self.position_slider.setFixedHeight(20)\n        self.position_slider.setPageStep(0)\n        self.position_slider.mousePressEvent = lambda e: self._on_slider_click(e, self.position_slider)\n        control_layout.addWidget(self.position_slider, stretch=1)'
)
print('  [slider click] OK')

# QSplitter 样式
c = c.replace(
    'content_splitter.setStyleSheet("QSplitter::handle { width: 1px; background: #21262D; }")',
    'content_splitter.setStyleSheet("QSplitter::handle { width: 4px; background: #90CAF9; border-radius: 2px; }")\n        content_splitter.setCollapsible(0, False)'
)
print('  [QSplitter] OK')

# 音量和字幕按钮
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

if 'volume_slider' not in c:
    c = c.replace(
        '        self.time_label.setStyleSheet("color: #8B949E; font-size: 12px;")\n        control_layout.addWidget(self.time_label)',
        '        self.time_label.setStyleSheet("color: #5D7A9C; font-size: 12px;")\n        control_layout.addWidget(self.time_label)' + vol_code
    )
    print('  [volume + subtitle buttons] OK')

# ═══════════════════════════════════════════════════════════════
# 第四部分：浅蓝主题颜色
# ═══════════════════════════════════════════════════════════════
print('\nApplying blue theme...')

theme_replacements = [
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
    # subtitle_panel 样式
    ('        self.subtitle_panel.setStyleSheet("""\n            background-color: #161B22;\n            border: 1px solid #21262D;',
     '        self.subtitle_panel.setStyleSheet("""\n            background-color: #FFFFFF;\n            border: 1px solid #BBDEFB;'),
]
for old, new in theme_replacements:
    c = c.replace(old, new)
print('  [colors] OK')

# 窗口渐变背景
c = c.replace(
    '        central_widget = QWidget()\n        self.setCentralWidget(central_widget)\n        main_layout = QVBoxLayout(central_widget)\n\n        self.setStyleSheet("""',
    '''        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 浅蓝渐变背景
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setBrush(self.backgroundRole(), QColor(245, 249, 255))
        self.setPalette(p)

        self.setStyleSheet("""'''
)
print('  [gradient background] OK')

# 验证
if not verify(c):
    print('\nFAILED - not saved')
    sys.exit(1)

save(c)
print('\nAll done! File saved.')

# 最终检查
import re
mp_refs = re.findall(r'media_player(?![\w_])', c)
qmp_refs = re.findall(r'QMediaPlayer', c)
dark_refs = re.findall(r'#0D1117|#161B22|#21262D', c)
print(f'  media_player refs: {len(mp_refs)}')
print(f'  QMediaPlayer refs: {len(qmp_refs)}')
print(f'  dark color refs: {len(dark_refs)}')
print(f'  Total lines: {len(c.splitlines())}')
