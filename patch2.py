import re

content = open('gui/main_window.py', encoding='utf-8').read()

# _add_to_history: 不再置顶，只原地更新
old = (
    '    def _add_to_history(self, title: str, file_path: str, duration: Optional[int] = None) -> None:\n'
    '        """添加视频到历史记录（去重，最新的放最前面）"""\n'
    '        file_path = os.path.abspath(file_path)\n\n'
    '        # 去重：如果已存在则移到最前面，并更新元信息\n'
    '        existing_entry = None\n'
    '        remaining = []\n'
    '        for h in self._video_history:\n'
    '            if h.get("path") == file_path:\n'
    '                existing_entry = h\n'
    '            else:\n'
    '                remaining.append(h)\n\n'
    '        # 构造记录（保留已有信息，用新信息覆盖）\n'
    '        entry = existing_entry or {}\n'
    '        # 安全保护：禁止 \'stream\' 作为标题（流媒体临时文件名泄漏）\n'
    '        safe_fallback = os.path.splitext(os.path.basename(file_path))[0]\n'
    '        if safe_fallback.lower() in ("stream", "视频"):\n'
    '            safe_fallback = existing_entry.get("title", "视频") if existing_entry else "视频"\n'
    '        entry.update({\n'
    '            "title": title or entry.get("title", safe_fallback),\n'
    '            "path": file_path,\n'
    '            "duration": duration if duration is not None else entry.get("duration"),\n'
    '            "time": time.strftime("%Y-%m-%d %H:%M"),\n'
    '        })\n'
    '        # 移除 local 标记，表示已被正式播放/下载过\n'
    '        entry.pop("source", None)\n\n'
    '        self._video_history = [entry] + remaining\n\n'
    '        # 最多保留 100 条\n'
    '        self._video_history = self._video_history[:100]\n\n'
    '        self._refresh_history_list()\n'
    '        self._save_history()'
)

new = (
    '    def _add_to_history(self, title: str, file_path: str, duration: Optional[int] = None) -> None:\n'
    '        """添加视频到历史记录（去重，不改变原有顺序，只更新元数据）"""\n'
    '        file_path = os.path.abspath(file_path)\n\n'
    '        # 查找是否已存在\n'
    '        existing_idx = None\n'
    '        for i, h in enumerate(self._video_history):\n'
    '            if h.get("path") == file_path:\n'
    '                existing_idx = i\n'
    '                break\n\n'
    '        safe_fallback = os.path.splitext(os.path.basename(file_path))[0]\n'
    '        if safe_fallback.lower() in ("stream", "视频"):\n'
    '            safe_fallback = (self._video_history[existing_idx].get("title", "视频")\n'
    '                             if existing_idx is not None else "视频")\n\n'
    '        entry = {\n'
    '            "title": (title or\n'
    '                      (self._video_history[existing_idx].get("title", safe_fallback)\n'
    '                       if existing_idx is not None else safe_fallback)),\n'
    '            "path": file_path,\n'
    '            "duration": (duration if duration is not None else\n'
    '                         (self._video_history[existing_idx].get("duration")\n'
    '                          if existing_idx is not None else None)),\n'
    '            "time": time.strftime("%Y-%m-%d %H:%M"),\n'
    '        }\n'
    '        entry.pop("source", None)\n\n'
    '        if existing_idx is not None:\n'
    '            # 已存在：原地更新元数据，不改变列表顺序\n'
    '            self._video_history[existing_idx].update(entry)\n'
    '        else:\n'
    '            # 新视频：追加到末尾（不置顶，保持原有顺序）\n'
    '            self._video_history.append(entry)\n\n'
    '        # 最多保留 100 条\n'
    '        self._video_history = self._video_history[:100]\n\n'
    '        self._refresh_history_list()\n'
    '        self._save_history()'
)

if old in content:
    content = content.replace(old, new)
    print('Patched: _add_to_history no-reorder')
else:
    print('WARN: _add_to_history pattern not found')

open('gui/main_window.py', 'w', encoding='utf-8').write(content)
print('done')
