content = open('gui/main_window.py', encoding='utf-8').read()

# 1. _load_video 中启用音量控件（第一次出现）
old1 = '''# 启用播放控制
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.position_slider.setEnabled(True)

        title = os.path.splitext(os.path.basename(file_path))[0]'''
new1 = '''# 启用播放控制
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.position_slider.setEnabled(True)
        self.volume_slider.setEnabled(True)
        self.volume_up_btn.setEnabled(True)
        self.volume_down_btn.setEnabled(True)

        title = os.path.splitext(os.path.basename(file_path))[0]'''
if old1 in content:
    content = content.replace(old1, new1, 1)
    print('Patched: volume enable in _load_video')
else:
    print('WARN: pattern 1 not found')

# 2. _stop_playback 中禁用音量控件
old2 = 'self.subtitle_toggle_btn.setEnabled(False)'
new2 = '''self.subtitle_toggle_btn.setEnabled(False)
        self.volume_slider.setEnabled(False)
        self.volume_up_btn.setEnabled(False)
        self.volume_down_btn.setEnabled(False)'''
if old2 in content:
    content = content.replace(old2, new2, 1)
    print('Patched: volume disable in _stop_playback')
else:
    print('WARN: pattern 2 not found')

# 3. 历史列表不置顶：在 _refresh_history_list 中移除 takeItem/insertItem(0)
# 找到 _refresh_history_list，移除 current_row 相关的置顶逻辑
old3 = '''if current_row >= 0:
                self.history_list.takeItem(current_row)
                self.history_list.insertItem(0, list_item)
                self.history_list.setCurrentRow(0)
            else:
                self.history_list.addItem(list_item)'''
new3 = '''self.history_list.addItem(list_item)'''
if old3 in content:
    content = content.replace(old3, new3)
    print('Patched: history no auto-pin')
else:
    print('WARN: pattern 3 not found')

open('gui/main_window.py', 'w', encoding='utf-8').write(content)
print('All done')
