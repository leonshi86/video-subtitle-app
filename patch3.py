import re

content = open('gui/main_window.py', encoding='utf-8').read()

new_method = '''
    def _add_to_history(self, title: str, file_path: str, duration: Optional[int] = None) -> None:
        """添加视频到历史记录（去重，不改变原有顺序，只更新元数据）"""
        file_path = os.path.abspath(file_path)

        # 查找是否已存在
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
            # 已存在：原地更新元数据，不改变列表顺序
            self._video_history[existing_idx].update(entry)
        else:
            # 新视频：追加到末尾（不置顶，保持原有顺序）
            self._video_history.append(entry)

        # 最多保留 100 条
        self._video_history = self._video_history[:100]

        self._refresh_history_list()
        self._save_history()
'''

# Match from "def _add_to_history" to "self._save_history()"
pattern = r'(    def _add_to_history\(self, title: str, file_path: str, duration: Optional\[int\] = None\) -> None:\n        """添加视频到历史记录.*?""")\n        file_path = os\.path\.abspath\(file_path\)\n\n        # 去重.*?\n        existing_entry = None\n        remaining = \[\]\n        for h in self\._video_history:\n            if h\.get\("path"\) == file_path:\n                existing_entry = h\n            else:\n                remaining\.append\(h\)\n\n        # 构造记录.*?\n        entry = existing_entry or \{\}\n        # 安全保护.*?\n        safe_fallback = os\.path\.splitext\(os\.path\.basename\(file_path\)\)\[0\]\n        if safe_fallback\.lower\(\) in \("stream", "视频"\):\n            safe_fallback = existing_entry\.get\("title", "视频"\) if existing_entry else "视频"\n        entry\.update\(\{\n            "title": title or entry\.get\("title", safe_fallback\),\n            "path": file_path,\n            "duration": duration if duration is not None else entry\.get\("duration"\),\n            "time": time\.strftime\("%Y-%m-%d %H:%M"\),\n        \}\)\n        # 移除 local 标记.*?\n        entry\.pop\("source", None\)\n\n        self\._video_history = \[entry\] \+ remaining\n\n        # 最多保留 100 条\n        self\._video_history = self\._video_history\[:100\]\n\n        self\._refresh_history_list\(\)\n        self\._save_history\(\)'

result = re.subn(pattern, new_method.strip(), content, flags=re.DOTALL)
if result[0]:
    print(f'Patched: _add_to_history ({result[1]} replacement(s))')
else:
    print('WARN: pattern not found, trying simpler approach')
    # Simpler: replace the specific problematic line
    old_line = '        self._video_history = [entry] + remaining'
    new_line = '        # 已存在则原地更新（不置顶）；新视频追加到末尾'
    if old_line in content:
        content = content.replace(old_line, new_line, 1)
        print('Patched: simple replacement done')

open('gui/main_window.py', 'w', encoding='utf-8').write(content)
print('done')
