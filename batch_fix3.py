#!/usr/bin/env python3
"""剩余批次修复"""
import ast

PATH = 'gui/main_window.py'

def load(): return open(PATH, encoding='utf-8').read()
def save(c): open(PATH, 'w', encoding='utf-8').write(c)

def verify(c): 
    try: ast.parse(c); return True
    except SyntaxError as e: print(f'SYNTAX ERROR line {e.lineno}: {e.msg}'); return False

def apply(c, old, new, tag):
    if old not in c: print(f'  [{tag}] SKIP'); return c
    new_c = c.replace(old, new, 1)
    if verify(new_c): print(f'  [{tag}] OK'); return new_c
    raise Exception(f'[{tag}] Failed')

c = load()

# 批次16：_add_to_history 不置顶（检查实际内容）
if 'self._video_history = [entry] + remaining' in c:
    c = apply(c,
        'self._video_history = [entry] + remaining',
        '# 已存在则原地更新，新视频追加末尾',
        'add_history_logic')
    save(c)
else:
    print('  [add_history] already fixed')

# 批次17：closeEvent
c = load()
if 'self.media_player.stop()' in c:
    c = apply(c,
        '        self.media_player.stop()',
        '        if hasattr(self, "_vlc_player") and self._vlc_player:\n            self._vlc_player.stop()\n        if hasattr(self, "_vlc_instance") and self._vlc_instance:\n            self._vlc_instance.release()',
        'close_event')
    save(c)

# 批次18：_on_media_status_changed
c = load()
if '@Slot("QMediaPlayer::MediaStatus")' in c:
    lines = c.split('\n')
    for i, l in enumerate(lines):
        if '@Slot("QMediaPlayer::MediaStatus")' in l:
            # 找到方法结束
            end = i + 1
            while end < len(lines):
                if lines[end].startswith('    def ') and '_on_media_status' not in lines[end]:
                    break
                end += 1
            lines = lines[:i] + [
                '    def _on_media_status_changed(self, status) -> None:',
                '        """VLC 不需要，状态由 _poll_vlc_state 处理"""',
                '        pass',
                ''
            ] + lines[end:]
            break
    c = '\n'.join(lines)
    if verify(c): save(c); print('  [media_status] OK')

# 批次19：_on_player_error
c = load()
if '@Slot(QMediaPlayer.Error, str)' in c:
    lines = c.split('\n')
    for i, l in enumerate(lines):
        if '@Slot(QMediaPlayer.Error, str)' in l:
            end = i + 1
            while end < len(lines):
                if lines[end].startswith('    def ') and '_on_player_error' not in lines[end]:
                    break
                end += 1
            lines = lines[:i] + [
                '    def _on_player_error(self, msg: str = "") -> None:',
                '        """播放器错误"""',
                '        logger.error("播放器错误: %s", msg)',
                ''
            ] + lines[end:]
            break
    c = '\n'.join(lines)
    if verify(c): save(c); print('  [player_error] OK')

# 批次20：_load_video 启用控件
c = load()
c = apply(c,
    '        self.position_slider.setEnabled(True)\n\n        title = os.path.splitext',
    '        self.position_slider.setEnabled(True)\n        self.volume_slider.setEnabled(True)\n        self.volume_up_btn.setEnabled(True)\n        self.volume_down_btn.setEnabled(True)\n        self.subtitle_toggle_btn.setEnabled(True)\n\n        title = os.path.splitext',
    'enable_controls')
save(c)

# 批次21：_on_position_changed 节流
c = load()
c = apply(c,
    '    def _on_position_changed(self, position_ms: int) -> None:\n        """播放位置变化 → 更新字幕"""\n\n        # 更新滑块',
    '    def _on_position_changed(self, position_ms: int) -> None:\n        """播放位置变化 → 更新字幕"""\n        # 节流：80ms\n        last = self._sync_last_pos_ms\n        delta = position_ms - last if last >= 0 else 999999\n        if delta >= 0 and delta < 80:\n            return\n        self._sync_last_pos_ms = position_ms\n\n        # 更新滑块',
    'throttle')
save(c)

# 批次22：移除 @Slot 装饰器
c = load()
c = c.replace('    @Slot()\n    def _toggle_playback', '    def _toggle_playback', 1)
c = c.replace('    @Slot(int)\n    def _seek_position', '    def _seek_position', 1)
c = c.replace('    @Slot(int)\n    def _on_position_changed', '    def _on_position_changed', 1)
c = c.replace('    @Slot(int)\n    def _on_duration_changed', '    def _on_duration_changed', 1)
c = c.replace('    @Slot()\n    def _stop_playback', '    def _stop_playback', 1)
if verify(c): save(c); print('  [cleanup_slots] OK')

# 批次23：QSplitter handle
c = load()
c = apply(c,
    'content_splitter.setStyleSheet("QSplitter::handle { width: 1px; background: #21262D; }")',
    'content_splitter.setStyleSheet("QSplitter::handle { width: 4px; background: #90CAF9; border-radius: 2px; }")\n        content_splitter.setCollapsible(0, False)',
    'splitter')
save(c)

# 最终验证
c = load()
if verify(c):
    print('\n全部批次完成！')
else:
    print('\n存在语法错误')
