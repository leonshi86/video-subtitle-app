import ast
c = open('gui/main_window.py', encoding='utf-8').read()

# 替换 _on_state_changed（注意：@Slot 有4空格缩进，def 也有4空格）
old_state = '''    @Slot(QMediaPlayer.PlaybackState)
    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        """播放状态变化"""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText("⏸ 暂停")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.play_btn.setText("▶ 播放")
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            self.play_btn.setText("▶ 播放")
            self.current_subtitle_label.setVisible(False)
            self._highlight_subtitle_row(-1)
        # 刷新历史列表，同步 ▶ 播放指示
        self._refresh_history_list()'''

new_state = '''    def _on_vlc_state_changed(self, new_state: vlc.State) -> None:
        if new_state == vlc.State.Playing:
            self.play_btn.setText("⏸ 暂停")
        elif new_state == vlc.State.Paused:
            self.play_btn.setText("▶ 播放")
        elif new_state in (vlc.State.Stopped, vlc.State.Ended):
            self.play_btn.setText("▶ 播放")
            self.current_subtitle_label.setVisible(False)
            self._highlight_subtitle_row(-1)
        self._refresh_history_list()'''

c = c.replace(old_state, new_state)

# 替换 _on_media_status_changed
old_ms = '''    @Slot("QMediaPlayer::MediaStatus")
    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        """媒体状态变化 → 控制加载提示"""
        logger.info("媒体状态: %s", status)
        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            self._hide_loading()
            title = os.path.splitext(os.path.basename(self.media_player.source().toLocalFile()))[0]
            self.status_label.setText(f"已加载: {title}")

            # 如果有待播放的请求，自动开始播放
            if self._auto_play_pending:
                self._auto_play_pending = False
                self._toggle_playback()'''

new_ms = '''    def _on_media_status_changed(self, status) -> None:
        pass'''

c = c.replace(old_ms, new_ms)

# 替换 _on_player_error
old_err = '''    @Slot(QMediaPlayer.Error, str)
    def _on_player_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        """播放器错误"""
        logger.error(
            "播放器错误: code=%s msg=%s source=%s",
            error, error_string,
            self.media_player.source().toString(),
        )
        QMessageBox.warning(self, "播放错误", f"{error_string}\\n\\n源: {self.media_player.source().toString()}")'''

new_err = '''    def _on_player_error(self, msg: str = "") -> None:
        logger.error("播放器错误: %s", msg)'''

c = c.replace(old_err, new_err)

ast.parse(c)
open('gui/main_window.py', 'w', encoding='utf-8').write(c)
print('Done')
