#!/usr/bin/env python3
"""分批工业级修复：每批验证语法"""
import ast, sys

PATH = 'gui/main_window.py'

def load(): return open(PATH, encoding='utf-8').read()
def save(c): 
    open(PATH, 'w', encoding='utf-8').write(c)

def verify(c, tag):
    try:
        ast.parse(c)
        return True
    except SyntaxError as e:
        print(f'[{tag}] SYNTAX ERROR line {e.lineno}: {e.msg}')
        return False

def apply(c, old, new, tag):
    if old not in c:
        print(f'  [{tag}] SKIP (not found)')
        return c
    new_c = c.replace(old, new, 1)
    if verify(new_c, tag):
        print(f'  [{tag}] OK')
        return new_c
    raise Exception(f'[{tag}] Failed')

# ═══════════════════════════════════════════════════════════════
# 批次1：imports
# ═══════════════════════════════════════════════════════════════
c = load()
c = apply(c, 
    'from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput',
    'import vlc  # VLC 播放器',
    'import_vlc')
c = apply(c,
    'from PySide6.QtMultimediaWidgets import QVideoWidget',
    '# QVideoWidget 移除（VLC 迁移）',
    'import_widget')
save(c)
print('批次1完成')

# ═══════════════════════════════════════════════════════════════
# 批次2：video_widget 和 _setup_media_player
# ═══════════════════════════════════════════════════════════════
c = load()
c = apply(c,
    '        self.video_widget = QVideoWidget()',
    '        self.video_widget = QWidget()',
    'video_widget')

# _setup_media_player 完整替换
old_setup = '''    # ── 媒体播放器初始化 ───────────────────────────────────────────────────
    def _setup_media_player(self) -> None:
        """初始化 QMediaPlayer 和音频输出"""

        # 注：禁用硬件解码的环境变量 QT_MULTIMEDIA_PREFER_SOFTWARE=1
        # 已在 main.py 的 QApplication 创建前设置，此处无需重复。

        # 音频输出（Qt 6.2+ 必需）
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0.8)

        # 媒体播放器
        self.media_player = QMediaPlayer()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)

        # 错误处理
        self.media_player.errorOccurred.connect(self._on_player_error)'''

new_setup = '''    # ── 媒体播放器初始化 ───────────────────────────────────────────────────
    def _setup_media_player(self) -> None:
        """初始化 VLC 媒体播放器（全局禁用内嵌字幕）"""
        self._vlc_instance = vlc.Instance(
            "--network-caching=1000",
            "--file-caching=500",
            "--avcodec-hw=any",
            "--no-spu",
            "--no-sub-autodetect-file",
            "--verbose=0",
        )
        self._vlc_player = self._vlc_instance.media_player_new()
        if sys.platform == "win32":
            self._vlc_player.set_hwnd(self.video_widget.winId())
        elif sys.platform == "darwin":
            self._vlc_player.set_nsobject(int(self.video_widget.winId()))
        self._vlc_player.audio_set_volume(80)
        
        # 轮询定时器
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(80)
        self._poll_timer.timeout.connect(self._poll_vlc_state)
        self._poll_timer.start()
        self._vlc_prev_state = None
        self._vlc_prev_media = None'''

c = apply(c, old_setup, new_setup, 'setup_media')
save(c)
print('批次2完成')

# ═══════════════════════════════════════════════════════════════
# 批次3：移除信号连接，添加状态变量初始化
# ═══════════════════════════════════════════════════════════════
c = load()
c = apply(c,
    '''        # 播放器状态变化
        self.media_player.positionChanged.connect(self._on_position_changed)
        self.media_player.durationChanged.connect(self._on_duration_changed)
        self.media_player.playbackStateChanged.connect(self._on_state_changed)
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)''',
    '        # VLC 状态通过 _poll_timer 轮询',
    'signals')
c = apply(c,
    '        self._auto_play_pending: bool = False',
    '        self._auto_play_pending: bool = False\n        self._sync_last_pos_ms: int = -1  # 字幕同步节流',
    'sync_init')
save(c)
print('批次3完成')

# ═══════════════════════════════════════════════════════════════
# 批次4：media_player → _vlc_player 替换
# ═══════════════════════════════════════════════════════════════
c = load()
c = apply(c, 'self.media_player.play()', 'self._vlc_player.play()', 'play')
c = apply(c, 'self.media_player.pause()', 'self._vlc_player.pause()', 'pause')
c = apply(c, 'self.media_player.stop()', 'self._vlc_player.stop()', 'stop')
c = apply(c, 'self.media_player.setPosition(position)', 'self._vlc_player.set_time(position)', 'seek')
c = apply(c, 'self.media_player.duration()', 'self._vlc_player.get_length()', 'duration')
save(c)
print('批次4完成')

# ═══════════════════════════════════════════════════════════════
# 批次5：_load_video 和 _set_media_source
# ═══════════════════════════════════════════════════════════════
c = load()
c = apply(c,
    '        media_source = QUrl.fromLocalFile(file_path)\n        logger.info("媒体源 URI: %s", media_source.toString())\n        self.media_player.setSource(media_source)',
    '        media = self._vlc_instance.media_new(file_path)\n        self._vlc_player.set_media(media)\n        logger.info("VLC 媒体源: %s", file_path)',
    'load_video')
save(c)
print('批次5完成')

# ═══════════════════════════════════════════════════════════════
# 批次6：_toggle_playback
# ═══════════════════════════════════════════════════════════════
c = load()
old_toggle = '''    @Slot()
    def _toggle_playback(self) -> None:
        """切换播放/暂停"""
        from PySide6.QtWidgets import QApplication

        state = self.media_player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_btn.setText("▶ 播放")
        else:'''
new_toggle = '''    def _toggle_playback(self) -> None:
        """切换播放/暂停"""
        from PySide6.QtWidgets import QApplication
        state = self._vlc_player.get_state()
        if state == vlc.State.Playing:
            self._vlc_player.pause()
            self.play_btn.setText("▶ 播放")
        else:'''
c = apply(c, old_toggle, new_toggle, 'toggle_playback')

# 移除 source().isValid() 检查
c = apply(c,
    'if self._current_video_path and not self.media_player.source().isValid():',
    'if self._current_video_path and self._vlc_player.get_media() is None:',
    'source_check')
save(c)
print('批次6完成')

# ═══════════════════════════════════════════════════════════════
# 批次7：_stop_playback
# ═══════════════════════════════════════════════════════════════
c = load()
old_stop = '''    @Slot()
    def _stop_playback(self) -> None:
        """停止播放"""
        self.media_player.stop()
        self.play_btn.setText("▶ 播放")
        # 隐藏当前字幕
        self.current_subtitle_label.setVisible(False)
        # 停止后恢复转写
        if self._transcribe_thread and self._transcribe_thread.isRunning():
            logger.info("停止后恢复转写线程")
            self._transcribe_worker.resume()'''
new_stop = '''    def _stop_playback(self) -> None:
        """停止播放"""
        self._vlc_player.stop()
        self.play_btn.setText("▶ 播放")
        self.position_slider.setValue(0)
        self._sync_last_pos_ms = -1
        self.volume_slider.setEnabled(False)
        self.volume_up_btn.setEnabled(False)
        self.volume_down_btn.setEnabled(False)
        self.subtitle_toggle_btn.setEnabled(False)'''
c = apply(c, old_stop, new_stop, 'stop_playback')
save(c)
print('批次7完成')

# ═══════════════════════════════════════════════════════════════
# 批次8：_on_state_changed → _on_vlc_state_changed
# ═══════════════════════════════════════════════════════════════
c = load()
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
        """播放状态变化"""
        if new_state == vlc.State.Playing:
            self.play_btn.setText("⏸ 暂停")
        elif new_state == vlc.State.Paused:
            self.play_btn.setText("▶ 播放")
        elif new_state == vlc.State.Stopped or new_state == vlc.State.Ended:
            self.play_btn.setText("▶ 播放")
            self.current_subtitle_label.setVisible(False)
            self._highlight_subtitle_row(-1)
        self._refresh_history_list()'''
c = apply(c, old_state, new_state, 'state_changed')
save(c)
print('批次8完成')

print('\n前8批次完成，继续后续批次...')
