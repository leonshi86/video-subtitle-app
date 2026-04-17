c = open('gui/main_window.py', encoding='utf-8').read()

# 1. 修复 _set_media_source 中残留的 media_source (QUrl)
c = c.replace(
    'self._vlc_player.set_media(self._vlc_instance.media_new(media_source))',
    'self._vlc_player.set_media(self._vlc_instance.media_new(file_path))'
)
# 修复日志
c = c.replace(
    'logger.info("媒体源 URI: %s", media_source.toString())',
    'logger.info("VLC 媒体源: %s", file_path)'
)
# 删除无用的 media_source 变量
c = c.replace(
    '        # 设置媒体源（用 file:/// URI）\n        media_source = QUrl.fromLocalFile(file_path)\n        logger.info("VLC 媒体源: %s", file_path)',
    '        # 设置媒体源\n        logger.info("VLC 媒体源: %s", file_path)'
)

import ast
ast.parse(c)
open('gui/main_window.py', 'w', encoding='utf-8').write(c)
print('Fixed')
