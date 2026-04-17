import ast
c = open('gui/main_window.py', encoding='utf-8').read()

# 1. _load_video 中的 setSource
c = c.replace(
    '        # 设置媒体源\n        logger.info("VLC 媒体源: %s", file_path)\n        self.media_player.setSource(media_source)',
    '        # 设置媒体源\n        media = self._vlc_instance.media_new(file_path)\n        self._vlc_player.set_media(media)\n        logger.info("VLC 媒体源: %s", file_path)'
)

# 2. _load_and_play 中的 setSource
c = c.replace(
    '        media_source = QUrl.fromLocalFile(file_path)\n        logger.info("设置媒体源: %s", media_source.toString())\n        self.media_player.setSource(media_source)',
    '        media = self._vlc_instance.media_new(file_path)\n        self._vlc_player.set_media(media)\n        logger.info("VLC 媒体源: %s", file_path)'
)

# 3. _on_state_changed → _on_vlc_state_changed
lines = c.split('\n')
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
            '            self.play_btn.setText("\u23f8 \u505c\u6b62")',
            '        elif new_state == vlc.State.Paused:',
            '            self.play_btn.setText("\u25b6 \u64ad\u653e")',
            '        elif new_state in (vlc.State.Stopped, vlc.State.Ended):',
            '            self.play_btn.setText("\u25b6 \u64ad\u653e")',
            '            self.current_subtitle_label.setVisible(False)',
            '            self._highlight_subtitle_row(-1)',
            '        self._refresh_history_list()',
            ''
        ] + lines[end:]
        print(f'Fixed _on_state_changed at line {i+1}')
        break
c = '\n'.join(lines)

# 4. 清理注释中的 QMediaPlayer 引用
c = c.replace('初始化 QMediaPlayer 和音频输出', '初始化 VLC 媒体播放器')

ast.parse(c)
open('gui/main_window.py', 'w', encoding='utf-8').write(c)
print('All residuals fixed')
