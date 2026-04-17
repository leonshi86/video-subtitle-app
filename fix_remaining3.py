c = open('gui/main_window.py', encoding='utf-8').read()

# 修复缩进问题
c = c.replace(
    '        logger.info("媒体源 URI: %s", media_source.toString())\n        media = self._vlc_instance.media_new(file_path)\n            self._vlc_player.set_media(media)',
    '        logger.info("VLC 媒体源: %s", file_path)\n        media = self._vlc_instance.media_new(file_path)\n        self._vlc_player.set_media(media)'
)

# 修复剩余的 media_player 引用
c = c.replace('self.media_player.playbackState()', 'self._vlc_player.get_state()')
c = c.replace('QMediaPlayer.PlaybackState.PlayingState', 'vlc.State.Playing')
c = c.replace('QMediaPlayer.PlaybackState.PausedState', 'vlc.State.Paused')
c = c.replace('QMediaPlayer.PlaybackState.StoppedState', 'vlc.State.Stopped')

# 修复 _set_media_source 中的残留
old_set = '''        media_source = QUrl.fromLocalFile(file_path)
        logger.info("媒体源 URI: %s", media_source.toString())
        self.media_player.setSource(media_source)'''
new_set = '''        media = self._vlc_instance.media_new(file_path)
        self._vlc_player.set_media(media)
        logger.info("VLC 媒体源: %s", file_path)'''
c = c.replace(old_set, new_set)

import ast
ast.parse(c)
open('gui/main_window.py', 'w', encoding='utf-8').write(c)
print('Fixed all remaining issues')
