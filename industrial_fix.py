#!/usr/bin/env python3
"""工业级修复脚本：解决所有架构问题"""
import ast

PATH = 'gui/main_window.py'

def load(): return open(PATH, encoding='utf-8').read()
def save(c): open(PATH, 'w', encoding='utf-8').write(c)

def do(old, new, tag=''):
    c = load()
    if old not in c:
        print(f'  SKIP [{tag}]')
        return False
    c = c.replace(old, new, 1)
    ast.parse(c)
    save(c)
    print(f'  OK [{tag}]')
    return True

# ═══════════════════════════════════════════════════════════════
# 批次1：修复 QMediaPlayer → VLC 残留引用
# ═══════════════════════════════════════════════════════════════

# 1. _toggle_playback 中的 VLC playbackState 检查
do(
    'state = self.media_player.playbackState()\n        if new_state == vlc.State.Playing:',
    'state = self._vlc_player.get_state()\n        if state == vlc.State.Playing:',
    'toggle_state'
)

# 2. media_player.source().isValid() 残留
do(
    'if self._current_video_path and not self.media_player.source().isValid():',
    'if self._current_video_path and self._vlc_player.get_media() is None:',
    'source_valid'
)

# 3. _set_media_source 中的 setSource
do(
    'self.media_player.setSource(media_source)',
    'media = self._vlc_instance.media_new(file_path)\n            self._vlc_player.set_media(media)',
    'setSource'
)

# 4. _on_vlc_state_changed 中的 QMediaPlayer 引用
do(
    'if state == QMediaPlayer.PlaybackState.PlayingState:',
    'if new_state == vlc.State.Playing:',
    'vlc_state'
)

# 5. closeEvent 中的 media_player
do(
    '        self.media_player.stop()',
    '        if hasattr(self, "_vlc_player") and self._vlc_player:\n            self._vlc_player.stop()\n        if hasattr(self, "_vlc_instance") and self._vlc_instance:\n            self._vlc_instance.release()',
    'closeEvent'
)

# 6. _on_player_error 简化
do(
    '''    @Slot(QMediaPlayer.Error, str)
    def _on_player_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        """播放器错误"""
        logger.error(
            "播放器错误: code=%s msg=%s source=%s",
            error, error_string,
            self.media_player.source().toString(),
        )
        QMessageBox.warning(self, "播放错误", f"{error_string}\\n\\n源: {self.media_player.source().toString()}")''',
    '''    def _on_player_error(self, msg: str = "") -> None:
        """播放器错误"""
        logger.error("播放器错误: %s", msg)
        if msg:
            QMessageBox.warning(self, "播放错误", msg)''',
    'player_error'
)

# 7. 移除未使用的 @Slot(QMediaPlayer.PlaybackState) 装饰器
do(
    '    @Slot(QMediaPlayer.PlaybackState)\n\n    def _poll_vlc_state',
    '\n    def _poll_vlc_state',
    'remove_decorator'
)

# ═══════════════════════════════════════════════════════════════
# 批次2：添加缺失的初始化和方法
# ═══════════════════════════════════════════════════════════════

# 8. 添加 _sync_last_pos_ms 初始化
c = load()
if 'self._sync_last_pos_ms = -1' not in c or 'self._sync_last_pos_ms: int = -1' not in c:
    # 在 __init__ 中添加初始化
    lines = c.split('\n')
    for i, l in enumerate(lines):
        if 'self._auto_play_pending: bool = False' in l:
            lines.insert(i+1, '        self._sync_last_pos_ms: int = -1  # 字幕同步节流用')
            break
    c = '\n'.join(lines)
    ast.parse(c)
    save(c)
    print('  OK [sync_init]')

# 9. 添加 _get_display_title 方法
get_title_method = '''
    def _get_display_title(self) -> str:
        """获取显示标题（优先下载标题，否则取文件名）"""
        if hasattr(self, "_download_title") and self._download_title:
            return self._download_title
        if self._current_video_path:
            name = os.path.splitext(os.path.basename(self._current_video_path))[0]
            if name.lower() not in ("stream", "视频"):
                return name
        return "视频"
'''

c = load()
if '_get_display_title' not in c:
    lines = c.split('\n')
    for i, l in enumerate(lines):
        if '    def _on_player_error' in l:
            lines.insert(i, get_title_method)
            break
    c = '\n'.join(lines)
    ast.parse(c)
    save(c)
    print('  OK [get_title]')

# 10. 添加 subtitle_toggle_btn 按钮（在下载控制栏）
c = load()
if 'subtitle_toggle_btn' not in c or 'self.subtitle_toggle_btn' not in c:
    lines = c.split('\n')
    # 找到 volume_layout 后面，添加字幕开关按钮
    for i, l in enumerate(lines):
        if 'control_layout.addLayout(volume_layout)' in l:
            # 在 volume control 后面添加字幕开关
            subtitle_btn_code = '''
        # 字幕开关按钮
        self.subtitle_toggle_btn = QPushButton("关字幕")
        self.subtitle_toggle_btn.setFixedHeight(32)
        self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #EF5350; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #E53935; } QPushButton:disabled { background-color: #E8F5E9; color: #A5D6A7; }")
        self.subtitle_toggle_btn.clicked.connect(self._toggle_subtitle_display)
        self.subtitle_toggle_btn.setEnabled(False)
        self._subtitle_panel_visible = True
        control_layout.addWidget(self.subtitle_toggle_btn)'''
            lines.insert(i+1, subtitle_btn_code)
            break
    c = '\n'.join(lines)
    ast.parse(c)
    save(c)
    print('  OK [subtitle_toggle_btn]')

# 11. 添加 80ms 节流到 _on_position_changed
c = load()
if 'last = self._sync_last_pos_ms' not in c:
    # 添加节流逻辑
    old_pos = '''    @Slot(int)
    def _on_position_changed(self, position_ms: int) -> None:
        """播放位置变化 → 更新字幕"""

        # 更新滑块'''
    new_pos = '''    def _on_position_changed(self, position_ms: int) -> None:
        """播放位置变化 → 更新字幕（80ms 节流避免高频刷新）"""

        # 更新滑块'''
    c = c.replace(old_pos, new_pos, 1)
    
    # 在字幕同步逻辑前添加节流
    old_sync = '''        # 同步字幕（只在播放且有字幕时显示）'''
    new_sync = '''        # ── 字幕同步：节流 ≥ 80ms ──
        last = self._sync_last_pos_ms
        delta = position_ms - last if last >= 0 else 999999
        is_seek = (delta < 0) or (delta > 500)
        if not is_seek and delta < 80:
            return
        self._sync_last_pos_ms = position_ms

        # 同步字幕（只在播放且有字幕时显示）'''
    c = c.replace(old_sync, new_sync, 1)
    
    ast.parse(c)
    save(c)
    print('  OK [throttle]')

# 12. 添加 _toggle_subtitle_display 方法
c = load()
if 'def _toggle_subtitle_display' not in c:
    toggle_method = '''
    # ── 字幕开关 ─────────────────────────────────────────────────────────
    def _toggle_subtitle_display(self) -> None:
        """字幕文本区显示/隐藏开关"""
        self._subtitle_panel_visible = not self._subtitle_panel_visible
        self.subtitle_panel.setVisible(self._subtitle_panel_visible)
        if self._subtitle_panel_visible:
            self.subtitle_toggle_btn.setText("关字幕")
            self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #EF5350; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #E53935; }")
        else:
            self.subtitle_toggle_btn.setText("开字幕")
            self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #66BB6A; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #43A047; }")

'''
    lines = c.split('\n')
    for i, l in enumerate(lines):
        if '    def _get_display_title' in l:
            lines.insert(i, toggle_method)
            break
    c = '\n'.join(lines)
    ast.parse(c)
    save(c)
    print('  OK [toggle_subtitle]')

# 13. 添加进度条点击和音量控制方法
c = load()
helpers = '''
    # ── 进度条点击定位 ─────────────────────────────────────────────────
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

'''
if '_on_slider_click' not in c:
    lines = c.split('\n')
    for i, l in enumerate(lines):
        if '    def _toggle_subtitle_display' in l:
            lines.insert(i, helpers)
            break
    c = '\n'.join(lines)
    ast.parse(c)
    save(c)
    print('  OK [helpers]')

# 14. 移除重复的 @Slot 装饰器
c = load()
c = c.replace('    @Slot(int)\n    def _on_position_changed', '    def _on_position_changed', 1)
c = c.replace('    @Slot(int)\n    def _on_duration_changed', '    def _on_duration_changed', 1)
c = c.replace('    @Slot(int)\n    def _seek_position', '    def _seek_position', 1)
ast.parse(c)
save(c)
print('  OK [cleanup_slots]')

# 最终验证
c = load()
try:
    ast.parse(c)
    print('\n工业级修复完成，语法正确。')
except SyntaxError as e:
    print(f'\n语法错误 line {e.lineno}: {e.msg}')
