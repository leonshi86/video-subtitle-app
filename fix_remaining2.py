#!/usr/bin/env python3
"""最终精确补丁：处理所有剩余未匹配项"""
import ast

PATH = 'gui/main_window.py'

def load(): return open(PATH, encoding='utf-8').read()
def save(c): open(PATH, 'w', encoding='utf-8').write(c)

def do(old, new, tag=''):
    c = load()
    if old not in c:
        print(f'  SKIP [{tag}]')
        return
    c = c.replace(old, new, 1)
    ast.parse(c)
    save(c)
    print(f'  OK [{tag}]')

# 1. _add_to_history（实际内容）
do('''    def _add_to_history(self, title: str, file_path: str, duration: Optional[int] = None) -> None:
        """添加视频到历史记录（去重，最新的放最前面）"""
        file_path = os.path.abspath(file_path)

        # 去重：如果已存在则移到最前面，并更新元信息
        existing_entry = None
        remaining = []
        for h in self._video_history:
            if h.get("path") == file_path:
                existing_entry = h
            else:
                remaining.append(h)

        # 构造记录（保留已有信息，用新信息覆盖）
        entry = existing_entry or {}
        entry.update({
            "title": title or entry.get("title", os.path.basename(file_path)),
            "path": file_path,
            "duration": duration if duration is not None else entry.get("duration"),
            "time": time.strftime("%Y-%m-%d %H:%M"),
        })
        # 移除 local 标记，表示已被正式播放/下载过
        entry.pop("source", None)

        self._video_history = [entry] + remaining

        # 最多保留 100 条
        self._video_history = self._video_history[:100]

        self._refresh_history_list()
        self._save_history()''',
'''    def _add_to_history(self, title: str, file_path: str, duration: Optional[int] = None) -> None:
        """添加视频到历史记录（去重，不改变原有顺序，只更新元数据）"""
        file_path = os.path.abspath(file_path)

        existing_idx = None
        for i, h in enumerate(self._video_history):
            if h.get("path") == file_path:
                existing_idx = i
                break

        safe_fallback = os.path.splitext(os.path.basename(file_path))[0]
        if safe_fallback.lower() in ("stream", "视频"):
            safe_fallback = (self._video_history[existing_idx].get("title", "视频")
                            if existing_idx is not None else "视频")

        entry = {
            "title": (title or
                      (self._video_history[existing_idx].get("title", safe_fallback)
                       if existing_idx is not None else safe_fallback)),
            "path": file_path,
            "duration": (duration if duration is not None else
                         (self._video_history[existing_idx].get("duration")
                          if existing_idx is not None else None)),
            "time": time.strftime("%Y-%m-%d %H:%M"),
        }
        entry.pop("source", None)

        if existing_idx is not None:
            self._video_history[existing_idx].update(entry)
        else:
            self._video_history.append(entry)

        self._video_history = self._video_history[:100]

        self._refresh_history_list()
        self._save_history()''', 'add_history')

# 2. _on_media_status_changed
do('''    @Slot("QMediaPlayer::MediaStatus")
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
                self._toggle_playback()''',
'''    def _on_media_status_changed(self, status) -> None:
        """VLC 不需要，状态由 _poll_vlc_state 处理"""
        pass''', 'media_status')

# 3. _on_player_error
do('''    @Slot(QMediaPlayer.Error, str)
    def _on_player_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        """播放器错误"""
        logger.error(
            "播放器错误: code=%s msg=%s source=%s",
            error, error_string,
            getattr(self.media_player, "source", lambda: None)(),
        )''',
'''    def _on_player_error(self, msg: str) -> None:
        logger.error("播放错误: %s", msg)''', 'player_error')

# 4. subtitle_toggle_btn 初始状态（找到它的实际位置）
c = load()
# Find the line that connects subtitle_toggle_btn.clicked
for line in c.split('\n'):
    if 'subtitle_toggle_btn.clicked.connect' in line:
        # Find position and insert setEnabled after
        idx = c.find(line)
        new = line + '\n        self.subtitle_toggle_btn.setEnabled(False)\n        self._subtitle_panel_visible = True'
        c2 = c.replace(line, new, 1)
        ast.parse(c2)
        save(c2)
        print('  OK [toggle-init]')
        break

# Final
c = load()
try:
    ast.parse(c)
    print('\nAll done. Final syntax OK.')
except SyntaxError as e:
    print(f'\nFINAL ERROR line {e.lineno}: {e.msg}')
    print(c.split('\n')[e.lineno-2:e.lineno+1])
