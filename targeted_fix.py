#!/usr/bin/env python3
"""针对性修复：插入缺失方法 + 清理所有残留引用"""
import ast, re

PATH = 'gui/main_window.py'
src = open(PATH, encoding='utf-8').read()
lines = src.split('\n')

# ═══════════════════════════════════════════════════════════════
# 1. 清理所有 self.media_player 残留引用
# ═══════════════════════════════════════════════════════════════
# 替换 self.media_player.source().isValid() → VLC 等效
c = src
c = c.replace('self.media_player.source().isValid()', 'self._vlc_player.get_media() is not None')
c = c.replace('self.media_player.source().toString()', '(self._current_video_path or "")')
c = c.replace('self.media_player.source().toLocalFile()', '(self._current_video_path or "")')
c = c.replace('self.media_player.playbackState()', 'self._vlc_player.get_state()')
c = c.replace('self.media_player.playbackState()', 'self._vlc_player.get_state()')  # 第二次替换覆盖遗漏
c = c.replace('QMediaPlayer.PlaybackState.PlayingState', 'vlc.State.Playing')
c = c.replace('QMediaPlayer.PlaybackState.PausedState', 'vlc.State.Paused')
c = c.replace('QMediaPlayer.PlaybackState.StoppedState', 'vlc.State.Stopped')
c = c.replace('QMediaPlayer.MediaStatus.LoadedMedia', 'vlc.State.Playing')
c = c.replace('QMediaPlayer.MediaStatus.BufferedMedia', 'vlc.State.Playing')
print(f'  [cleanup] replaced media_player refs')

# ═══════════════════════════════════════════════════════════════
# 2. 清理深色颜色
# ═══════════════════════════════════════════════════════════════
dark_to_light = [
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
for old, new in dark_to_light:
    c = c.replace(old, new)
print(f'  [theme] replaced dark colors')

# ═══════════════════════════════════════════════════════════════
# 3. 插入缺失的方法（在 _setup_ui 之后、_load_video 之前）
# ═══════════════════════════════════════════════════════════════
new_methods = '''
    # ═══════════════════════════════════════════════════════════
    # VLC 轮询 & 辅助方法
    # ═══════════════════════════════════════════════════════════
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

    def _on_slider_click(self, event, slider):
        """进度条任意位置点击时精准跳转"""
        if slider.maximum() == 0:
            return
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
        """字幕文本区显示/隐藏开关"""
        self._subtitle_panel_visible = not self._subtitle_panel_visible
        self.subtitle_panel.setVisible(self._subtitle_panel_visible)
        if self._subtitle_panel_visible:
            self.subtitle_toggle_btn.setText("关字幕")
            self.subtitle_toggle_btn.setStyleSheet(
                "QPushButton { background-color: #EF5350; border: none; border-radius: 6px; "
                "color: white; font-size: 12px; font-weight: bold; } "
                "QPushButton:hover { background-color: #E53935; }"
            )
        else:
            self.subtitle_toggle_btn.setText("开字幕")
            self.subtitle_toggle_btn.setStyleSheet(
                "QPushButton { background-color: #66BB6A; border: none; border-radius: 6px; "
                "color: white; font-size: 12px; font-weight: bold; } "
                "QPushButton:hover { background-color: #43A047; }"
            )

'''

# 在 _setup_ui 结束处、_load_video 开始处插入
for i, l in enumerate(c.split('\n')):
    if '    def _load_video(self, file_path' in l and i > 50:
        # 往前找 _setup_ui 的结束（下一个 def）
        for j in range(i-1, max(0, i-20), -1):
            if c.split('\n')[j].startswith('    # ── 媒体播放器') or \
               (c.split('\n')[j].startswith('    def ') and '_setup_ui' in c.split('\n')[j-1] if j > 0 else False):
                break
        # 在 _load_video 前插入
        parts = c.split('\n')
        parts = parts[:i] + [new_methods] + parts[i:]
        c = '\n'.join(parts)
        print(f'  [methods] inserted before line {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 4. subtitle_panel self 属性
# ═══════════════════════════════════════════════════════════════
c = c.replace('        subtitle_panel = QWidget()', '        self.subtitle_panel = QWidget()')
c = c.replace('subtitle_layout = QVBoxLayout(subtitle_panel)', 'subtitle_layout = QVBoxLayout(self.subtitle_panel)')
c = c.replace('right_layout.addWidget(subtitle_panel)', 'right_layout.addWidget(self.subtitle_panel)')

# subtitle_panel 样式
c = c.replace(
    'self.subtitle_panel.setStyleSheet(\n            background-color: #161B22;\n            border: 1px solid #21262D;',
    'self.subtitle_panel.setStyleSheet(\n            background-color: #FFFFFF;\n            border: 1px solid #BBDEFB;'
)

# ═══════════════════════════════════════════════════════════════
# 5. 历史面板最小宽度
# ═══════════════════════════════════════════════════════════════
c = c.replace(
    '        history_panel = QWidget()\n        history_panel.setStyleSheet',
    '        history_panel = QWidget()\n        history_panel.setMinimumWidth(180)\n        history_panel.setStyleSheet'
)

# ═══════════════════════════════════════════════════════════════
# 6. 进度条点击支持
# ═══════════════════════════════════════════════════════════════
c = c.replace(
    '        self.position_slider.setFixedHeight(20)\n        control_layout.addWidget(self.position_slider, stretch=1)',
    '        self.position_slider.setFixedHeight(20)\n        self.position_slider.setPageStep(0)\n        self.position_slider.mousePressEvent = lambda e: self._on_slider_click(e, self.position_slider)\n        control_layout.addWidget(self.position_slider, stretch=1)'
)

# ═══════════════════════════════════════════════════════════════
# 7. QSplitter 样式
# ═══════════════════════════════════════════════════════════════
c = c.replace(
    'content_splitter.setStyleSheet("QSplitter::handle { width: 1px; background: #21262D; }")',
    'content_splitter.setStyleSheet("QSplitter::handle { width: 4px; background: #90CAF9; border-radius: 2px; }")\n        content_splitter.setCollapsible(0, False)'
)

# ═══════════════════════════════════════════════════════════════
# 8. 窗口渐变背景
# ═══════════════════════════════════════════════════════════════
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

# ═══════════════════════════════════════════════════════════════
# 9. 音量和字幕按钮（在 time_label 后）
# ═══════════════════════════════════════════════════════════════
vol_code = '''
        # 音量控制
        volume_layout = QHBoxLayout()
        volume_layout.setSpacing(4)
        self.volume_down_btn = QPushButton("-")
        self.volume_down_btn.setFixedSize(26, 26)
        self.volume_down_btn.setStyleSheet(
            "QPushButton { background-color: #90CAF9; border: none; border-radius: 4px; "
            "color: white; font-size: 14px; font-weight: bold; } "
            "QPushButton:hover { background-color: #42A5F5; } "
            "QPushButton:disabled { background-color: #E3F2FD; color: #90CAF9; }"
        )
        self.volume_down_btn.clicked.connect(self._adjust_volume_down)
        self.volume_down_btn.setEnabled(False)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.setEnabled(False)
        self.volume_slider.setStyleSheet(
            "QSlider::groove:horizontal { height: 4px; background: #BBDEFB; border-radius: 2px; } "
            "QSlider::handle:horizontal { width: 10px; background: #42A5F5; border-radius: 5px; margin: -3px 0; } "
            "QSlider::sub-page:horizontal { background: #42A5F5; border-radius: 2px; }"
        )
        self.volume_slider.valueChanged.connect(self._on_volume_slider_changed)
        self.volume_up_btn = QPushButton("+")
        self.volume_up_btn.setFixedSize(26, 26)
        self.volume_up_btn.setStyleSheet(
            "QPushButton { background-color: #90CAF9; border: none; border-radius: 4px; "
            "color: white; font-size: 14px; font-weight: bold; } "
            "QPushButton:hover { background-color: #42A5F5; } "
            "QPushButton:disabled { background-color: #E3F2FD; color: #90CAF9; }"
        )
        self.volume_up_btn.clicked.connect(self._adjust_volume_up)
        self.volume_up_btn.setEnabled(False)
        volume_layout.addWidget(self.volume_down_btn)
        volume_layout.addWidget(self.volume_slider)
        volume_layout.addWidget(self.volume_up_btn)
        control_layout.addLayout(volume_layout)
        self.subtitle_toggle_btn = QPushButton("关字幕")
        self.subtitle_toggle_btn.setFixedHeight(32)
        self.subtitle_toggle_btn.setStyleSheet(
            "QPushButton { background-color: #EF5350; border: none; border-radius: 6px; "
            "color: white; font-size: 12px; font-weight: bold; } "
            "QPushButton:hover { background-color: #E53935; } "
            "QPushButton:disabled { background-color: #E8F5E9; color: #A5D6A7; }"
        )
        self.subtitle_toggle_btn.clicked.connect(self._toggle_subtitle_display)
        self.subtitle_toggle_btn.setEnabled(False)
        self._subtitle_panel_visible = True
        control_layout.addWidget(self.subtitle_toggle_btn)'''

if 'volume_slider' not in c:
    c = c.replace(
        '        self.time_label.setStyleSheet("color: #5D7A9C; font-size: 12px;")\n        control_layout.addWidget(self.time_label)',
        '        self.time_label.setStyleSheet("color: #5D7A9C; font-size: 12px;")\n        control_layout.addWidget(self.time_label)' + vol_code
    )
    print('  [volume_buttons] inserted')

# ═══════════════════════════════════════════════════════════════
# 10. 启用控件
# ═══════════════════════════════════════════════════════════════
c = c.replace(
    '        self.position_slider.setEnabled(True)\n\n        title = os.path.splitext',
    '        self.position_slider.setEnabled(True)\n        self.volume_slider.setEnabled(True)\n        self.volume_up_btn.setEnabled(True)\n        self.volume_down_btn.setEnabled(True)\n        self.subtitle_toggle_btn.setEnabled(True)\n\n        title = os.path.splitext'
)
print('  [enable_controls] done')

# ═══════════════════════════════════════════════════════════════
# 验证
# ═══════════════════════════════════════════════════════════════
try:
    ast.parse(c)
    print('  Syntax OK')
    open(PATH, 'w', encoding='utf-8').write(c)
    print('  Saved')
except SyntaxError as e:
    print(f'  SYNTAX ERROR line {e.lineno}: {e.msg}')

# 残留检查
mp = re.findall(r'self\.media_player(?![\w_])', c)
qmp = re.findall(r'QMediaPlayer\.', c)
dark = re.findall(r'#0D1117|#161B22|#21262D', c)
print(f'  media_player refs: {len(mp)}, QMediaPlayer: {len(qmp)}, dark: {len(dark)}')

# 方法检查
tree = ast.parse(c)
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == 'MainWindow':
        methods = {item.name: item.lineno for item in node.body if isinstance(item, ast.FunctionDef)}
        required = ['_poll_vlc_state', '_get_display_title', '_on_slider_click', 
                    '_adjust_volume_up', '_adjust_volume_down', '_on_volume_slider_changed',
                    '_toggle_subtitle_display', '_on_vlc_state_changed', '_setup_media_player']
        for m in required:
            status = 'OK' if m in methods else 'MISSING'
            print(f'  {m}: {status}')
        break
