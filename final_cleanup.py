#!/usr/bin/env python3
"""最终清理：处理 final_migrate.py 之后的所有残留"""
import ast, re

PATH = 'gui/main_window.py'
src = open(PATH, encoding='utf-8').read()
lines = src.split('\n')

# ═══════════════════════════════════════════════════════════════
# 清理所有 self.media_player / QMediaPlayer 残留
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    # 替换所有 QMediaPlayer.PlaybackState.xxx
    if 'QMediaPlayer.PlaybackState.PlayingState' in l:
        lines[i] = l.replace('QMediaPlayer.PlaybackState.PlayingState', 'vlc.State.Playing')
    if 'QMediaPlayer.PlaybackState.PausedState' in l:
        lines[i] = l.replace('QMediaPlayer.PlaybackState.PausedState', 'vlc.State.Paused')
    if 'QMediaPlayer.PlaybackState.StoppedState' in l:
        lines[i] = l.replace('QMediaPlayer.PlaybackState.StoppedState', 'vlc.State.Stopped')
    if 'QMediaPlayer.MediaStatus.' in l:
        lines[i] = l.replace('QMediaPlayer.MediaStatus.LoadedMedia', 'vlc.State.Playing').replace('QMediaPlayer.MediaStatus.BufferedMedia', 'vlc.State.Playing')
    if 'QMediaPlayer.Error' in l:
        lines[i] = l.replace('QMediaPlayer.Error', 'str')
    # media_player.source() 替换
    if 'self.media_player.source().toLocalFile()' in l:
        lines[i] = l.replace('self.media_player.source().toLocalFile()', '(self._current_video_path or "")')
    if 'self.media_player.source().toString()' in l:
        lines[i] = l.replace('self.media_player.source().toString()', '(self._current_video_path or "")')
    if 'self.media_player.source().isValid()' in l:
        lines[i] = l.replace('self.media_player.source().isValid()', 'self._vlc_player.get_media() is not None')
    if 'self.media_player.playbackState()' in l:
        lines[i] = l.replace('self.media_player.playbackState()', 'self._vlc_player.get_state()')
    if 'self.media_player.play()' in l:
        lines[i] = l.replace('self.media_player.play()', 'self._vlc_player.play()')
    if 'self.media_player.pause()' in l:
        lines[i] = l.replace('self.media_player.pause()', 'self._vlc_player.pause()')
    if 'self.media_player.stop()' in l:
        lines[i] = l.replace('self.media_player.stop()', 'self._vlc_player.stop()')
    if 'self.media_player.setPosition(position)' in l:
        lines[i] = l.replace('self.media_player.setPosition(position)', 'self._vlc_player.set_time(position)')
    if 'self.media_player.duration()' in l:
        lines[i] = l.replace('self.media_player.duration()', 'self._vlc_player.get_length()')
    if 'self.media_player.setSource(' in l:
        lines[i] = l.replace('self.media_player.setSource(media_source)', 'self._vlc_player.set_media(media)')
    # media_player = QMediaPlayer() → 删除行
    if 'self.media_player = QMediaPlayer()' in l:
        lines[i] = ''
    if 'self.media_player.setAudioOutput(self.audio_output)' in l:
        lines[i] = ''
    if 'self.media_player.setVideoOutput(self.video_widget)' in l:
        lines[i] = ''
    if 'self.media_player.errorOccurred.connect(self._on_player_error)' in l:
        lines[i] = ''
    # 信号连接
    if 'self.media_player.positionChanged.connect(self._on_position_changed)' in l:
        lines[i] = ''
    if 'self.media_player.durationChanged.connect(self._on_duration_changed)' in l:
        lines[i] = ''
    if 'self.media_player.playbackStateChanged.connect(self._on_state_changed)' in l:
        lines[i] = ''
    if 'self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)' in l:
        lines[i] = ''

# 移除空行（由上面产生的）
new_lines = []
for l in lines:
    if l.strip() == '' and new_lines and new_lines[-1].strip() == '':
        continue
    new_lines.append(l)
lines = new_lines

# ═══════════════════════════════════════════════════════════════
# 替换 _on_state_changed（行级）
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if '@Slot(QMediaPlayer.PlaybackState)' in l and '_on_state_changed' in lines[i+1]:
        end = i + 1
        while end < len(lines):
            if lines[end].startswith('    def ') and '_on_state' not in lines[end]:
                break
            end += 1
        lines = lines[:i] + [
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
        ] + lines[end:]
        print(f'  [state_changed] at line {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 替换 _on_media_status_changed
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if '@Slot("QMediaPlayer::MediaStatus")' in l:
        end = i + 1
        while end < len(lines):
            if lines[end].startswith('    def ') and '_on_media' not in lines[end]:
                break
            end += 1
        lines = lines[:i] + ['    def _on_media_status_changed(self, status) -> None:', '        pass', ''] + lines[end:]
        print(f'  [media_status] at line {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 替换 _on_player_error
# ═══════════════════════════════════════════════════════════════
for i, l in enumerate(lines):
    if '@Slot(QMediaPlayer.Error, str)' in l:
        end = i + 1
        while end < len(lines):
            if lines[end].startswith('    # ──') and '\u5bfc\u51fa' in lines[end]:
                break
            end += 1
        lines = lines[:i] + ['    def _on_player_error(self, msg: str = "") -> None:', '        logger.error("播放器错误: %s", msg)', ''] + lines[end:]
        print(f'  [player_error] at line {i+1}')
        break

# ═══════════════════════════════════════════════════════════════
# 移除 @Slot 装饰器（剩余的）
# ═══════════════════════════════════════════════════════════════
slots = ['@Slot()', '@Slot(int)', '@Slot(float)', '@Slot(str)', '@Slot(object)', '@Slot(list)', '@Slot(QMediaPlayer.PlaybackState)', '@Slot("QMediaPlayer::MediaStatus")', '@Slot(QMediaPlayer.Error, str)']
new_lines = []
skip_next = False
for l in lines:
    stripped = l.strip()
    if skip_next:
        skip_next = False
        continue
    skip = False
    for slot in slots:
        if stripped == slot:
            skip = True
            skip_next = True
            break
    if skip:
        print(f'  [slot] removed: {stripped}')
        continue
    new_lines.append(l)
lines = new_lines

# ═══════════════════════════════════════════════════════════════
# 验证和保存
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

# 残留检查
mp = re.findall(r'self\.media_player(?![\w_])', c)
qmp = re.findall(r'QMediaPlayer\.', c)
dark = re.findall(r'#0D1117|#161B22|#21262D', c)
print(f'  media_player refs: {len(mp)}, QMediaPlayer: {len(qmp)}, dark: {len(dark)}')
if mp:
    for m in mp[:5]:
        idx = c.index(m)
        print(f'    ...{repr(c[max(0,idx-30):idx+40])}')
if qmp:
    for q in qmp[:5]:
        idx = c.index(q)
        print(f'    ...{repr(c[max(0,idx-30):idx+40])}')
