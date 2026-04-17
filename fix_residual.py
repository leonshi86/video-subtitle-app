c = open('gui/main_window.py', encoding='utf-8').read()

# 替换所有 media_player 残留为 _vlc_player
replacements = [
    ('self.media_player.setSource(media_source)', 'self._vlc_player.set_media(self._vlc_instance.media_new(file_path))'),
    ('state = self.media_player.playbackState()', 'state = self._vlc_player.get_state()'),
    ('if state == QMediaPlayer.PlaybackState.PlayingState:', 'if state == vlc.State.Playing:'),
    ('self.media_player.pause()', 'self._vlc_player.pause()'),
    ('if self._current_video_path and not self.media_player.source().isValid():', 'if self._current_video_path and self._vlc_player.get_media() is None:'),
    ('self.media_player.play()', 'self._vlc_player.play()'),
    ('self.media_player.stop()', 'self._vlc_player.stop()'),
    ('self.media_player.setPosition(position)', 'self._vlc_player.set_time(position)'),
    ('duration = self.media_player.duration()', 'duration = self._vlc_player.get_length()'),
    ('self.media_player.source().toLocalFile()', 'self._current_video_path or ""'),
    ('QMediaPlayer.MediaStatus.LoadedMedia', 'vlc.State.Playing'),
    ('QMediaPlayer.MediaStatus.BufferedMedia', 'vlc.State.Playing'),
    ('QMediaPlayer.PlaybackState.PlayingState', 'vlc.State.Playing'),
]

for old, new in replacements:
    c = c.replace(old, new)

# 移除 _on_media_status_changed 中的残留
import re
# 找到方法并替换
lines = c.split('\n')
for i, l in enumerate(lines):
    if 'def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus)' in l:
        # 找到方法结束
        end = i + 1
        while end < len(lines):
            if lines[end].startswith('    def ') and '_on_media' not in lines[end]:
                break
            end += 1
        # 替换
        lines = lines[:i] + [
            '    def _on_media_status_changed(self, status) -> None:',
            '        """VLC 不需要，状态由 _poll_vlc_state 处理"""',
            '        pass',
            ''
        ] + lines[end:]
        break
c = '\n'.join(lines)

# 处理历史双击中的 media_player
c = c.replace(
    'if self.media_player.playbackState() == vlc.State.Playing:',
    'if self._vlc_player.get_state() == vlc.State.Playing:'
)

import ast
ast.parse(c)
open('gui/main_window.py', 'w', encoding='utf-8').write(c)
print('Fixed')
