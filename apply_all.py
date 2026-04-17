#!/usr/bin/env python3
"""顺序应用所有功能修改，每次 patch 后重新计算行号"""
import ast

def read():
    return open('gui/main_window.py', encoding='utf-8').read()

def write(content):
    open('gui/main_window.py', 'w', encoding='utf-8').write(content)

def check(content, name):
    try:
        ast.parse(content)
        print(f'  [{name}] Syntax OK')
    except SyntaxError as e:
        print(f'  [{name}] SYNTAX ERROR line {e.lineno}: {e.msg}')
        raise

def find(content, text, after=None):
    lines = content.split('\n')
    idx = 0
    if after:
        for i, l in enumerate(lines):
            if after in l:
                idx = i + 1
                break
    for i in range(idx, len(lines)):
        if text in lines[i]:
            return i
    return -1

def insert_after(content, needle, code, name=''):
    idx = find(content, needle)
    if idx < 0:
        print(f'  WARN: [{name}] needle not found: {needle!r}')
        return content
    lines = content.split('\n')
    lines.insert(idx + 1, code)
    new = '\n'.join(lines)
    print(f'  [{name}] inserted at line {idx+1}')
    return new

def replace_block(content, start_text, end_text, new_block, name=''):
    """Replace a block of code between two markers"""
    lines = content.split('\n')
    start = find(content, start_text)
    if start < 0:
        print(f'  WARN: [{name}] start not found: {start_text!r}')
        return content
    # Find end: next method def at same indentation
    end = start + 1
    while end < len(lines):
        if lines[end].startswith('    def ') and end > start:
            break
        end += 1
    new_lines = lines[:start] + new_block.split('\n') + lines[end:]
    new = '\n'.join(new_lines)
    print(f'  [{name}] replaced lines {start}-{end-1}')
    return new

def replace_after(content, needle, new_block, name=''):
    """Replace from needle to next method def"""
    lines = content.split('\n')
    start = find(content, needle)
    if start < 0:
        print(f'  WARN: [{name}] needle not found')
        return content
    end = start + 1
    while end < len(lines):
        if lines[end].startswith('    def '):
            break
        end += 1
    new_lines = lines[:start] + new_block.split('\n') + lines[end:]
    new = '\n'.join(new_lines)
    print(f'  [{name}] replaced lines {start}-{end-1}')
    return new

c = read()
print('Applying patches...')

# ── P1: 进度条点击定位 ──
c = insert_after(c, 'self.position_slider.setFixedHeight(20)',
    '        self.position_slider.setPageStep(0)\n        self.position_slider.mousePressEvent = lambda e: self._on_slider_click(e, self.position_slider)',
    'P1')
check(c, 'P1')

# ── P2: 音量控制 UI ──
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
c = insert_after(c, 'control_layout.addWidget(self.time_label)', volume_code.strip(), 'P2')
check(c, 'P2')

# ── P3: _load_video 启用音量控件 ──
# 找 _load_video 中的 position_slider.setEnabled(True)
# (use after to distinguish from other places)
c = insert_after(c, 'self.position_slider.setEnabled(True)',
    '        self.volume_slider.setEnabled(True)\n        self.volume_up_btn.setEnabled(True)\n        self.volume_down_btn.setEnabled(True)',
    'P3')
check(c, 'P3')

# ── P4: _stop_playback 禁用音量控件 ──
c = insert_after(c, 'self.subtitle_toggle_btn.setEnabled(False)',
    '        self.volume_slider.setEnabled(False)\n        self.volume_up_btn.setEnabled(False)\n        self.volume_down_btn.setEnabled(False)',
    'P4')
check(c, 'P4')

# ── P5: 历史面板最小宽度 ──
c = insert_after(c, '        history_panel = QWidget()',
    "        history_panel.setMinimumWidth(180)  # 拖动分割线时最小宽度", 'P5')
check(c, 'P5')

# ── P6: QSplitter 配置 ──
c = insert_after(c, "content_splitter.setStyleSheet",
    "        content_splitter.setCollapsible(0, False)\n        content_splitter.setHandleWidth(4)", 'P6')
check(c, 'P6')

# ── P7: _add_to_history 不置顶 ──
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

        # 最多保留 100 条
        self._video_history = self._video_history[:100]

        self._refresh_history_list()
        self._save_history()'''

c = replace_after(c, '    def _add_to_history(self, title: str, file_path: str, duration: Optional[int] = None) -> None:',
    new_add_history, 'P7')
check(c, 'P7')

# ── P8: 新增方法（进度条点击 + 音量控制）─
new_methods = '''    # ── 进度条点击定位 ─────────────────────────────────────────────────
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

# Insert before _toggle_subtitle_display
toggle_idx = find(c, '    def _toggle_subtitle_display(self)')
if toggle_idx >= 0:
    lines = c.split('\n')
    lines.insert(toggle_idx, new_methods)
    c = '\n'.join(lines)
    print(f'  [P8] inserted new methods at line {toggle_idx}')
check(c, 'P8')

write(c)
print('All done.')
