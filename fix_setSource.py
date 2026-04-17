c = open('gui/main_window.py', encoding='utf-8').read()

# 修复 setSource 残留
c = c.replace(
    '        self._show_loading()\n        self.status_label.setText("正在加载视频…")\n\n        # 设置媒体源（用 file:/// URI）\n        media_source = QUrl.fromLocalFile(file_path)\n        logger.info("媒体源 URI: %s", media_source.toString())\n        self._vlc_player.set_media(self._vlc_instance.media_new(media_source))',
    '        self._show_loading()\n        self.status_label.setText("正在加载视频…")\n\n        # 设置媒体源\n        media = self._vlc_instance.media_new(file_path)\n        self._vlc_player.set_media(media)\n        logger.info("VLC 媒体源: %s", file_path)'
)

import ast
ast.parse(c)
open('gui/main_window.py', 'w', encoding='utf-8').write(c)
print('Fixed')
