import ast
c = open('gui/main_window.py', encoding='utf-8').read()

# 替换 _on_state_changed
c = c.replace(
    '@Slot(QMediaPlayer.PlaybackState)\n    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:\n        """播放状态变化"""\n        if state == QMediaPlayer.PlaybackState.PlayingState:\n            self.play_btn.setText("⏸ 暂停")\n        elif state == QMediaPlayer.PlaybackState.PausedState:\n            self.play_btn.setText("▶ 播放")\n        elif state == QMediaPlayer.PlaybackState.StoppedState:\n            self.play_btn.setText("▶ 播放")\n            self.current_subtitle_label.setVisible(False)\n            self._highlight_subtitle_row(-1)\n        # 刷新历史列表，同步 ▶ 播放指示\n        self._refresh_history_list()',
    '    def _on_vlc_state_changed(self, new_state: vlc.State) -> None:\n        if new_state == vlc.State.Playing:\n            self.play_btn.setText("⏸ 暂停")\n        elif new_state == vlc.State.Paused:\n            self.play_btn.setText("▶ 播放")\n        elif new_state in (vlc.State.Stopped, vlc.State.Ended):\n            self.play_btn.setText("▶ 播放")\n            self.current_subtitle_label.setVisible(False)\n            self._highlight_subtitle_row(-1)\n        self._refresh_history_list()'
)

# 替换 _on_media_status_changed
c = c.replace(
    '    @Slot("QMediaPlayer::MediaStatus")\n    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:\n        """媒体状态变化 → 控制加载提示"""\n        logger.info("媒体状态: %s", status)\n        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):\n            self._hide_loading()\n            title = os.path.splitext(os.path.basename(self.media_player.source().toLocalFile()))[0]\n            self.status_label.setText(f"已加载: {title}")\n\n            # 如果有待播放的请求，自动开始播放\n            if self._auto_play_pending:\n                self._auto_play_pending = False\n                self._toggle_playback()',
    '    def _on_media_status_changed(self, status) -> None:\n        pass'
)

# 替换 _on_player_error
c = c.replace(
    '    @Slot(QMediaPlayer.Error, str)\n    def _on_player_error(self, error: QMediaPlayer.Error, error_string: str) -> None:\n        """播放器错误"""\n        logger.error(\n            "播放器错误: code=%s msg=%s source=%s",\n            error, error_string,\n            self.media_player.source().toString(),\n        )\n        QMessageBox.warning(self, "播放错误", f"{error_string}\\n\\n源: {self.media_player.source().toString()}")',
    '    def _on_player_error(self, msg: str = "") -> None:\n        logger.error("播放器错误: %s", msg)'
)

ast.parse(c)
open('gui/main_window.py', 'w', encoding='utf-8').write(c)
print('Done')
