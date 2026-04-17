import re

content = open('gui/main_window.py', encoding='utf-8').read()

# Simple reliable approach: replace the exact problematic lines
# Pattern 1: the reordering assignment
old1 = '        self._video_history = [entry] + remaining'
new1 = '        # 已存在则原地更新（不置顶）；新视频追加到末尾'
if old1 in content:
    content = content.replace(old1, new1, 1)
    print('Patched: removed [entry]+remaining reordering')

# Pattern 2: find/replace the entire method using line-by-line approach
# Remove the "去重：如果已存在则移到最前面" comment
old2 = '        # 去重：如果已存在则移到最前面，并更新元信息'
new2 = '        # 查找是否已存在（不改变列表顺序）'
if old2 in content:
    content = content.replace(old2, new2, 1)
    print('Patched: comment updated')

# Pattern 3: existing_entry = None / remaining = []
# Change logic: find existing by index instead
old3 = '        existing_entry = None\n        remaining = []\n        for h in self._video_history:\n            if h.get("path") == file_path:\n                existing_entry = h\n            else:\n                remaining.append(h)\n\n        # 构造记录（保留已有信息，用新信息覆盖）\n        entry = existing_entry or {}\n        # 安全保护：禁止 "stream" 作为标题（流媒体临时文件名泄漏）\n        safe_fallback = os.path.splitext(os.path.basename(file_path))[0]\n        if safe_fallback.lower() in ("stream", "视频"):\n            safe_fallback = existing_entry.get("title", "视频") if existing_entry else "视频"\n        entry.update({\n            "title": title or entry.get("title", safe_fallback),\n            "path": file_path,\n            "duration": duration if duration is not None else entry.get("duration"),\n            "time": time.strftime("%Y-%m-%d %H:%M"),\n        })\n        # 移除 local 标记，表示已被正式播放/下载过\n        entry.pop("source", None)\n\n        if existing_entry:'
new3 = '        existing_idx = None\n        for i, h in enumerate(self._video_history):\n            if h.get("path") == file_path:\n                existing_idx = i\n                break\n\n        safe_fallback = os.path.splitext(os.path.basename(file_path))[0]\n        if safe_fallback.lower() in ("stream", "视频"):\n            safe_fallback = (self._video_history[existing_idx].get("title", "视频")\n                            if existing_idx is not None else "视频")\n\n        entry = {\n            "title": (title or\n                      (self._video_history[existing_idx].get("title", safe_fallback)\n                       if existing_idx is not None else safe_fallback)),\n            "path": file_path,\n            "duration": (duration if duration is not None else\n                         (self._video_history[existing_idx].get("duration")\n                          if existing_idx is not None else None)),\n            "time": time.strftime("%Y-%m-%d %H:%M"),\n        }\n        entry.pop("source", None)\n\n        if existing_idx is not None:'
if old3 in content:
    content = content.replace(old3, new3)
    print('Patched: method body refactored')
else:
    print('WARN: pattern 3 not found')

open('gui/main_window.py', 'w', encoding='utf-8').write(content)
print('done')
