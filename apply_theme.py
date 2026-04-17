c = open('gui/main_window.py', encoding='utf-8').read()

# ═══════════════════════════════════════════════════════════════
# 1. 颜色批量替换：深色 → 浅蓝
# ═══════════════════════════════════════════════════════════════
replacements = [
    ('#0D1117', '#FFFFFF'),
    ('#161B22', '#FFFFFF'),
    ('#1C2128', '#FFFFFF'),
    ('#21262D', '#FFFFFF'),
    ('#30363D', '#BBDEFB'),
    ('color: #E6EDF3', 'color: #1E3A5F'),
    ('color: #8B949E', 'color: #5D7A9C'),
    ('color: #6E7681', 'color: #5D7A9C'),
    ('background: #30363D', 'background: #E3F2FD'),
    ('background: #21262D', 'background: #E3F2FD'),
    ('background-color: #21262D', 'background-color: #FFFFFF'),
    ('border-bottom: 1px solid #21262D', 'border-bottom: 1px solid #BBDEFB'),
    ('background-color: #238636', 'background-color: #4CAF50'),
    ('border: 1px solid #30363D', 'border: 1px solid #BBDEFB'),
]
for old, new in replacements:
    c = c.replace(old, new)

# ═══════════════════════════════════════════════════════════════
# 2. 窗口背景渐变（在 setStyleSheet 前加 setAutoFillBackground）
# ═══════════════════════════════════════════════════════════════
# 找到 __init__ 中 self.setAutoFillBackground(True) 附近的内容
# 先确保 QColor 被 import
if 'QColor' not in c:
    c = c.replace(
        'from PySide6.QtGui import QFont, QPalette, QColor',
        'from PySide6.QtGui import QFont, QPalette, QColor'
    )

# 在 self.setStyleSheet(""") 前面插入渐变设置（仅在 __init__ 的 setCentralWidget 之后）
# 在 central_widget 定义后、setStyleSheet 之前插入
old_central = '''        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.setStyleSheet("""'''
new_central = '''        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 浅蓝渐变背景
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setBrush(self.backgroundRole(), QColor(245, 249, 255))
        self.setPalette(p)

        self.setStyleSheet("""'''
c = c.replace(old_central, new_central)

import ast
ast.parse(c)
open('gui/main_window.py', 'w', encoding='utf-8').write(c)
print('Done')
