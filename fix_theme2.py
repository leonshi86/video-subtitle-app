c = open('gui/main_window.py', encoding='utf-8').read()

# 浅色背景文字修复
c = c.replace('color: #E6EDF3', 'color: #1E3A5F')

# 添加渐变背景
old_bg = 'self.setStyleSheet("""'
new_bg = '''self.setAutoFillBackground(True)
p = self.palette()
p.setBrush(self.backgroundRole(), QColor(245, 249, 255))
self.setPalette(p)
self.setStyleSheet("""'''
c = c.replace(old_bg, new_bg)

import ast
ast.parse(c)
open('gui/main_window.py', 'w', encoding='utf-8').write(c)
print('Done')
