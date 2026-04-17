import ast
c = open('gui/main_window.py', encoding='utf-8').read()

# 修复被截断的 _toggle_subtitle_display 方法
# 找到被截断的行并替换整个方法
broken = '            self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #66BB6A; border: none; border-radius: 6px; color: white; font-size: 12\n            self.play_btn.setText("'
fixed = '            self.subtitle_toggle_btn.setStyleSheet("QPushButton { background-color: #66BB6A; border: none; border-radius: 6px; color: white; font-size: 12px; font-weight: bold; } QPushButton:hover { background-color: #43A047; }")\n        self.play_btn.setText("'
c = c.replace(broken, fixed)

ast.parse(c)
open('gui/main_window.py', 'w', encoding='utf-8').write(c)
print('Fixed')
