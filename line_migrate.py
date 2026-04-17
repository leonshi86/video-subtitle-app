#!/usr/bin/env python3
"""
行级全量修复脚本 - VLC + 浅蓝主题
每个步骤基于当前文件状态，不依赖多行匹配
"""
import ast

PATH = 'gui/main_window.py'

def load(): return open(PATH, encoding='utf-8').read()
def save(c): open(PATH, 'w', encoding='utf-8').write(c)
def verify(c):
    try: ast.parse(c); return True
    except SyntaxError as e:
        print(f'SYNTAX ERROR line {e.lineno}: {e.msg}')
        return False

def apply(c, old, new, tag):
    if old not in c:
        print(f'  [{tag}] SKIP')
        return c
    new_c = c.replace(old, new, 1)
    if not verify(new_c):
        raise Exception(f'[{tag}] failed')
    print(f'  [{tag}] OK')
    return new_c

# ═══════════════════════════════════════════════════════════════
# 阶段 1：imports
# ═══════════════════════════════════════════════════════════════
c = load()
c = apply(c,
    'from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput',
    'import vlc',
    'import_vlc')
c = apply(c,
    'from PySide6.QtMultimediaWidgets import QVideoWidget',
    '# QVideoWidget removed',
    'import_videowidget')
c = apply(c,
    '        self.video_widget = QVideoWidget()',
    '        self.video_widget = QWidget()',
    'video_widget')
save(c)
print('Stage 1 done')

# ═══════════════════════════════════════════════════════════════
# 阶段 2：替换所有单行引用
# ═══════════════════════════════════════════════════════════════
c = load()
single_replacements = [
    ('self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState',
     'self._vlc_player.get_state() == vlc.State.Playing'),
    ('self.media_player.playbackState()',
     'self._vlc_player.get_state()'),
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
    ('self.media_player.playbackState() == vlc.State.Playing',
     'self._vlc_player.get_state() == vlc.State.Playing'),
]
for old, new in single_replacements:
    c = c.replace(old, new)
save(c)
print('Stage 2 done')

# ═══════════════════════════════════════════════════════════════
# 阶段 3：替换 setSource（两处）
# ═══════════════════════════════════════════════════════════════
c = load()
# 3a. _load_video 中的
c = apply(c,
    '        self._show_loading()\n        self.status_label.setText("正在加载视频…")\n\n        # 设置媒体源（用 file:/// URI）\n        media_source = QUrl.fromLocalFile(file_path)\n        logger.info("媒体源 URI: %s", media_source.toString())\n        self.media_player.setSource(media_source)',
    '        self._show_loading()\n        self.status_label.setText("正在加载视频…")\n\n        # 设置媒体源\n        media = self._vlc_instance.media_new(file_path)\n        self._vlc_player.set_media(media)\n        logger.info("VLC 媒体源: %s", file_path)',
    'setSource_load')
# 3b. _load_and_play 中的
c = apply(c,
    '        media_source = QUrl.fromLocalFile(file_path)\n        logger.info("设置媒体源: %s", media_source.toString())\n        self.media_player.setSource(media_source)',
    '        media = self._vlc_instance.media_new(file_path)\n        self._vlc_player.set_media(media)\n        logger.info("VLC 媒体源: %s", file_path)',
    'setSource_andplay')
save(c)
print('Stage 3 done')

# ═══════════════════════════════════════════════════════════════
# 阶段 4：替换 _setup_media_player（行级）
# ═══════════════════════════════════════════════════════════════
c = load()
lines = c.split('\n')
for i, l in enumerate(lines):
    if 'def _setup_media_player(self)' in l:
        # 找到方法体结束
        end = i + 1
        indent = '    '
        while end < len(lines):
            if lines[end].startswith('    # ──') and '信号' in lines[end]:
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
        print('  [setup_media] OK')
        break
c = '\n'.join(lines)
if verify(c): save(c)
print('Stage 4 done')

# ═══════════════════════════════════════════════════════════════
# 阶段 5：状态变量初始化
# ═══════════════════════════════════════════════════════════════
c = load()
c = apply(c,
    '        self._auto_play_pending: bool = False',
    '        self._auto_play_pending: bool = False\n        self._sync_last_pos_ms: int = -1',
    'sync_init')
save(c)
print('Stage 5 done')

# ═══════════════════════════════════════════════════════════════
# 阶段 6：移除信号连接
# ═══════════════════════════════════════════════════════════════
c = load()
c = apply(c,
    '''        # 播放器状态变化
        self.media_player.positionChanged.connect(self._on_position_changed)
        self.media_player.durationChanged.connect(self._on_duration_changed)
        self.media_player.playbackStateChanged.connect(self._on_state_changed)
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)''',
    '        # VLC 状态通过 _poll_timer 轮询，不需要 Qt 信号连接',
    'signals')
save(c)
print('Stage 6 done')

# ═══════════════════════════════════════════════════════════════
# 阶段 7：替换 _on_state_changed（行级）
# ═══════════════════════════════════════════════════════════════
c = load()
lines = c.split('\n')
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
        lines = lines[:i] + new_method + lines[end:]
        print(f'  [state_changed] OK at line {i+1}')
        break
c = '\n'.join(lines)
if verify(c): save(c)
print('Stage 7 done')

# ═══════════════════════════════════════════════════════════════
# 阶段 8：简化 _on_media_status_changed（行级）
# ═══════════════════════════════════════════════════════════════
c = load()
lines = c.split('\n')
for i, l in enumerate(lines):
    if '@Slot("QMediaPlayer::MediaStatus")' in l:
        end = i + 1
        while end < len(lines):
            if lines[end].startswith('    def ') and '_on_media' not in lines[end]:
                break
            end += 1
        lines = lines[:i] + [
            '    def _on_media_status_changed(self, status) -> None:',
            '        pass',
            '',
        ] + lines[end:]
        print(f'  [media_status] OK at line {i+1}')
        break
c = '\n'.join(lines)
if verify(c): save(c)
print('Stage 8 done')

# ═══════════════════════════════════════════════════════════════
# 阶段 9：简化 _on_player_error（行级）
# ═══════════════════════════════════════════════════════════════
c = load()
lines = c.split('\n')
for i, l in enumerate(lines):
    if '@Slot(QMediaPlayer.Error, str)' in l:
        end = i + 1
        while end < len(lines):
            if lines[end].startswith('    # ──') and '导出' in lines[end]:
                break
            end += 1
        lines = lines[:i] + [
            '    def _on_player_error(self, msg: str = "") -> None:',
            '        logger.error("播放器错误: %s", msg)',
            '',
        ] + lines[end:]
        print(f'  [player_error] OK at line {i+1}')
        break
c = '\n'.join(lines)
if verify(c): save(c)
print('Stage 9 done')

# ═══════════════════════════════════════════════════════════════
# 阶段 10：移除 @Slot 装饰器
# ═══════════════════════════════════════════════════════════════
c = load()
for slot in ['@Slot()', '@Slot(int)', '@Slot(float)', '@Slot(str)', '@Slot(object)', '@Slot(list)']:
    c = c.replace('    ' + slot + '\n    def', '    def')
save(c)
print('Stage 10 done')

# ═══════════════════════════════════════════════════════════════
# 阶段 11：closeEvent
# ═══════════════════════════════════════════════════════════════
c = load()
c = apply(c,
    '        self._vlc_player.stop()\n\n        # 停止后台线程',
    '        if hasattr(self, "_vlc_player") and self._vlc_player:\n            self._vlc_player.stop()\n        if hasattr(self, "_vlc_instance") and self._vlc_instance:\n            self._vlc_instance.release()\n\n        # 停止后台线程',
    'closeEvent')
save(c)
print('Stage 11 done')

# ═══════════════════════════════════════════════════════════════
# 阶段 12：_stop_playback
# ═══════════════════════════════════════════════════════════════
c = load()
c = apply(c,
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
        self.subtitle_toggle_btn.setEnabled(False)''',
    'stop_playback')
save(c)
print('Stage 12 done')

# ═══════════════════════════════════════════════════════════════
# 阶段 13：_load_video 启用控件
# ═══════════════════════════════════════════════════════════════
c = load()
c = apply(c,
    '        self.position_slider.setEnabled(True)\n\n        title = os.path.splitext',
    '        self.position_slider.setEnabled(True)\n        self.volume_slider.setEnabled(True)\n        self.volume_up_btn.setEnabled(True)\n        self.volume_down_btn.setEnabled(True)\n        self.subtitle_toggle_btn.setEnabled(True)\n\n        title = os.path.splitext',
    'enable_controls')
save(c)
print('Stage 13 done')

# ═══════════════════════════════════════════════════════════════
# 阶段 14：_add_to_history 不置顶
# ═══════════════════════════════════════════════════════════════
c = load()
c = apply(c,
    'self._video_history = [entry] + remaining',
    '# 不置顶：原地更新或追加',
    'no_reorder')
save(c)
print('Stage 14 done')

# ═══════════════════════════════════════════════════════════════
# 阶段 15：新增方法（行级插入）
# ═══════════════════════════════════════════════════════════════
c = load()
new_methods = [
    '    def _poll_vlc_state(self) -> None:',
    '        """轮询 VLC 播放器状态/进度"""',
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
    '                self.status_label.setText(f"已加载: {display_title}")',
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
    '            if name.lower() not in ("stream", "视频"):',
    '                return name',
    '        return "视频"',
    '',
    '    # ── 进度条点击定位 ─────────────────────────────────────────────────',
    '    def _on_slider_click(self, event, slider):',
    '        if slider.maximum() == 0: return',
    '        val = slider.minimum() + (slider.maximum() - slider.minimum()) * event.position().x() / slider.width()',
    '        slider.setValue(int(val))',
    '        self._seek_position(int(val))',
    '',
    '    # ── 音量控制 ─────────────────────────────────────────────────────────',
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
    '    # ── 字幕开关 ─────────────────────────────────────────────────────────',
    '    def _toggle_subtitle_display(self) -> None:',
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

lines = c.split('\n')
for i, l in enumerate(lines):
    if '    def _on_vlc_state_changed(self' in l:
        lines = lines[:i] + new_methods + lines[i:]
        print('  [new_methods] inserted OK')
        break
c = '\n'.join(lines)
if verify(c): save(c)
print('Stage 15 done')

# ═══════════════════════════════════════════════════════════════
# 阶段 16：UI 控件
# ═══════════════════════════════════════════════════════════════
c = load()
# subtitle_panel
c = apply(c, '        subtitle_panel = QWidget()', '        self.subtitle_panel = QWidget()', 'subtitle')
c = apply(c, 'subtitle_layout = QVBoxLayout(subtitle_panel)', 'subtitle_layout = QVBoxLayout(self.subtitle_panel)', 'subtitle2')
c = apply(c, 'right_layout.addWidget(subtitle_panel)', 'right_layout.addWidget(self.subtitle_panel)', 'subtitle3')
# history min width
c = apply(c,
    '        history_panel = QWidget()\n        history_panel.setStyleSheet',
    '        history_panel = QWidget()\n        history_panel.setMinimumWidth(180)\n        history_panel.setStyleSheet',
    'history')
# slider click
c = apply(c,
    '        self.position_slider.setFixedHeight(20)\n        control_layout.addWidget(self.position_slider, stretch=1)',
    '        self.position_slider.setFixedHeight(20)\n        self.position_slider.setPageStep(0)\n        self.position_slider.mousePressEvent = lambda e: self._on_slider_click(e, self.position_slider)\n        control_layout.addWidget(self.position_slider, stretch=1)',
    'slider')
# QSplitter
c = apply(c,
    'content_splitter.setStyleSheet("QSplitter::handle { width: 1px; background: #21262D; }")',
    'content_splitter.setStyleSheet("QSplitter::handle { width: 4px; background: #90CAF9; border-radius: 2px; }")\n        content_splitter.setCollapsible(0, False)',
    'splitter')
save(c)
print('Stage 16 done')

# ═══════════════════════════════════════════════════════════════
# 阶段 17：音量和字幕按钮
# ═══════════════════════════════════════════════════════════════
c = load()
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
    c = apply(c,
        '        self.time_label.setStyleSheet("color: #8B949E; font-size: 12px;")\n        control_layout.addWidget(self.time_label)',
        '        self.time_label.setStyleSheet("color: #5D7A9C; font-size: 12px;")\n        control_layout.addWidget(self.time_label)' + vol_code,
        'volume')
save(c)
print('Stage 17 done')

# ═══════════════════════════════════════════════════════════════
# 阶段 18：浅蓝主题颜色
# ═══════════════════════════════════════════════════════════════
c = load()
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
    c = c.replace(old, new)
save(c)
print('Stage 18 done')

# ═══════════════════════════════════════════════════════════════
# 阶段 19：窗口渐变背景
# ═══════════════════════════════════════════════════════════════
c = load()
c = apply(c,
    '        central_widget = QWidget()\n        self.setCentralWidget(central_widget)\n        main_layout = QVBoxLayout(central_widget)\n\n        self.setStyleSheet("""',
    '''        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 浅蓝渐变背景
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setBrush(self.backgroundRole(), QColor(245, 249, 255))
        self.setPalette(p)

        self.setStyleSheet("""''',
    'gradient')
save(c)
print('Stage 19 done')

# ═══════════════════════════════════════════════════════════════
# 最终验证
# ═══════════════════════════════════════════════════════════════
c = load()
if verify(c):
    save(c)
    print('\nAll 19 stages complete!')
else:
    print('\nFAILED')
    import sys; sys.exit(1)
