content = open('gui/main_window.py', encoding='utf-8').read()

# Find the _add_to_history method and replace it completely
import re

new_method = '''    def _add_to_history(self, title: str, file_path: str, duration: Optional[int] = None) -> None:
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

# Use a regex that matches the entire method from def to the next def
pattern = r'(    def _add_to_history\(self, title: str, file_path: str, duration: Optional\[int\] = None\) -> None:\n        """添加视频到历史记录.*?""")\n        file_path = os\.path\.abspath\(file_path\)\n\n(        # 查找.*?\n        existing_entry = None.*?)        # 最多保留 100 条\n        self\._video_history = self\._video_history\[:100\]\n\n        self\._refresh_history_list\(\)\n        self\._save_history\(\)'

replacement = r'\1\n        file_path = os.path.abspath(file_path)\n\n' + new_method.split('    def _add_to_history')[1].split('\n        self._refresh_history_list')[0].rstrip()

result = re.subn(pattern, replacement, content, flags=re.DOTALL)
if result[0]:
    print(f'Patched ({result[0]} replacement)')
else:
    print('Regex failed, trying line-based approach')

    # Line-based: find _add_to_history start/end by indentation
    lines = content.split('\n')
    start = end = -1
    for i, line in enumerate(lines):
        if '    def _add_to_history(self' in line:
            start = i
        elif start >= 0 and end < 0 and line.startswith('    def ') and i > start:
            end = i
            break

    if start >= 0 and end > 0:
        new_lines = lines[:start] + new_method.split('\n        self._refresh_history_list')[0].split('\n') + ['        self._refresh_history_list()', '        self._save_history()', '']
        # Fix: new_method already has self._refresh_history_list and self._save_history
        new_method_lines = new_method.split('\n')
        new_lines = lines[:start] + new_method_lines + lines[end:]
        content = '\n'.join(new_lines)
        print(f'Patched (line-based, {start}-{end})')
    else:
        print(f'ERROR: start={start}, end={end}')

open('gui/main_window.py', 'w', encoding='utf-8').write(content)
print('done')
