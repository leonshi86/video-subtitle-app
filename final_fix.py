c = open('gui/main_window.py', encoding='utf-8').read()
# 最终清理残留的 media_source
c = c.replace(
    'self._vlc_player.set_media(self._vlc_instance.media_new(media_source))',
    'self._vlc_player.set_media(self._vlc_instance.media_new(file_path))'
)
c = c.replace(
    'self._vlc_player.set_media(self._vlc_instance.media_new(file_path))\n        media',
    'self._vlc_player.set_media(self._vlc_instance.media_new(file_path))'
)
import ast
ast.parse(c)
open('gui/main_window.py', 'w', encoding='utf-8').write(c)
print('Done')
