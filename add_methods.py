import ast

PATH = 'gui/main_window.py'
c = open(PATH, encoding='utf-8').read()
lines = c.split('\n')

# ═══════════════════════════════════════════════════════════════
# 1. 插入缺失方法（在 _setup_ui 结束前、_load_video 开始处）
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

# 在 _load_video 前插入
for i, l in enumerate(lines):
    if '    def _load_video(self' in l:
        lines = lines[:i] + [new_methods] + lines[i:]
        print(f'  [methods] inserted before line {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 2. UI 控件修复
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if '        subtitle_panel = QWidget()' in l:
        lines[i] = '        self.subtitle_panel = QWidget()'
        print(f'  [subtitle_panel] at {i+1}')
    elif 'subtitle_layout = QVBoxLayout(subtitle_panel)' in l:
        lines[i] = 'subtitle_layout = QVBoxLayout(self.subtitle_panel)'
    elif 'right_layout.addWidget(subtitle_panel)' in l:
        lines[i] = 'right_layout.addWidget(self.subtitle_panel)'
    # subtitle_panel 样式
    elif 'self.subtitle_panel.setStyleSheet' in l:
        lines[i] = l.replace('#161B22', '#FFFFFF').replace('#21262D', '#BBDEFB')
        print(f'  [subtitle_style] at {i+1}')
    # history_panel min width
    elif '        history_panel = QWidget()' in l and i+1 < len(lines) and 'history_panel.setStyleSheet' in lines[i+1]:
        lines.insert(i+1, '        history_panel.setMinimumWidth(180)')
        print(f'  [history_min] at {i+1}')
        break
    # slider click
    elif 'self.position_slider.setFixedHeight(20)' in l and i+1 < len(lines) and 'control_layout.addWidget(self.position_slider' in lines[i+1]:
        lines.insert(i+1, '        self.position_slider.setPageStep(0)')
        lines.insert(i+2, '        self.position_slider.mousePressEvent = lambda e: self._on_slider_click(e, self.position_slider)')
        print(f'  [slider_click] at {i+1}')
        break
    # QSplitter
    elif 'content_splitter.setStyleSheet("QSplitter::handle { width: 1px; background: #21262D; }")' in l:
        lines[i] = 'content_splitter.setStyleSheet("QSplitter::handle { width: 4px; background: #90CAF9; border-radius: 2px; }")\n        content_splitter.setCollapsible(0, False)'
        print(f'  [splitter] at {i+1}')
        break
    # window gradient
    elif 'central_widget = QWidget()' in l and i+1 < len(lines) and 'self.setCentralWidget(central_widget)' in lines[i+1]:
        lines.insert(i+4, '        # 浅蓝渐变背景')
        lines.insert(i+5, '        self.setAutoFillBackground(True)')
        lines.insert(i+6, '        p = self.palette()')
        lines.insert(i+7, '        p.setBrush(self.backgroundRole(), QColor(245, 249, 255))')
        lines.insert(i+8, '        self.setPalette(p)')
        print(f'  [gradient] at {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 3. 音量和字幕按钮
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if 'self.time_label.setStyleSheet("color: #8B949E; font-size: 12px;")' in l and i+1 < len(lines) and 'control_layout.addWidget(self.time_label)' in lines[i+1]:
        vol_code = '''        self.time_label.setStyleSheet("color: #5D7A9C; font-size: 12px;")
        control_layout.addWidget(self.time_label)
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
        lines = lines[:i] + vol_code.split('\n') + lines[i+2:]
        print(f'  [volume_buttons] at {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 4. 启用控件
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if 'self.position_slider.setEnabled(True)' in l and l.strip() == 'self.position_slider.setEnabled(True)':
        # 检查下面是否是 title 开头
        if i+1 < len(lines) and 'title = os.path.splitext' in lines[i+1]:
            lines.insert(i+1, '        self.volume_slider.setEnabled(True)')
            lines.insert(i+2, '        self.volume_up_btn.setEnabled(True)')
            lines.insert(i+3, '        self.volume_down_btn.setEnabled(True)')
            lines.insert(i+4, '        self.subtitle_toggle_btn.setEnabled(True)')
            print(f'  [enable_controls] at {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 验证
# ═══════════════════════════════════════════════════════════════
c = '\n'.join(lines)
try:
    ast.parse(c)
    print('  Syntax OK')
    open(PATH, 'w', encoding='utf-8').write(c)
    print('  Saved')
except SyntaxError as e:
    print(f'  SYNTAX ERROR line {e.lineno}: {e.msg}')
    lines2 = c.split('\n')
    for k in range(max(0, e.lineno-3), min(len(lines2), e.lineno+3)):
        mark = '>>>' if k == e.lineno-1 else '   '
        print(f'{mark} {k+1}: {repr(lines2[k][:100])}')
