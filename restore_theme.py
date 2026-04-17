c = open('gui/main_window.py', encoding='utf-8').read()
orig = c

# ═══════════════════════════════════════════════════════════════
# 颜色映射：深色 → 浅蓝主题
# ═══════════════════════════════════════════════════════════════
replacements = [
    # 主背景
    ('#0D1117', '#FFFFFF'),
    ('#161B22', '#FFFFFF'),
    ('#1C2128', '#FFFFFF'),
    # 卡片/面板
    ('#21262D', '#FFFFFF'),
    # 边框
    ('#30363D', '#BBDEFB'),
    # 文字颜色
    ('#8B949E', '#5D7A9C'),
    ('#6E7681', '#5D7A9C'),
    # hover 状态
    ('#21262D; color: #E6EDF3', '#E3F2FD; color: #1E3A5F'),
    # 进度条
    ('background: #30363D', 'background: #E3F2FD'),
    # QListView 选中
    ('background-color: #21262D; color: #E6EDF3', 'background-color: #90CAF9; color: #FFFFFF'),
    # right_panel
    ('background-color: #0D1117', 'background-color: #FFFFFF'),
    # history_panel
    ('background-color: #0D1117;', 'background-color: #F5F9FF;'),
    # status_bar
    ('background-color: #161B22; border-top: 1px solid #21262D', 'background-color: #E3F2FD; border-top: 1px solid #BBDEFB'),
    # title_bar
    ('background-color: #161B22; border-bottom: 1px solid #21262D', 'background-color: #FFFFFF; border-bottom: 1px solid #BBDEFB'),
    # download_bar
    ('background-color: #161B22; border-bottom: 1px solid #21262D', 'background-color: #F5F9FF; border-bottom: 1px solid #BBDEFB'),
    # subtitle_panel
    ('background-color: #161B22;\n            border: 1px solid #21262D', 'background-color: #FFFFFF;\n            border: 1px solid #BBDEFB'),
    # right_panel (again)
    ('background-color: #0D1117;', 'background-color: #FFFFFF;'),
    # 滚动条
    ('background-color: #21262D', 'background-color: #E3F2FD'),
    # download_btn
    ('background-color: #238636', 'background-color: #4CAF50'),
    ('border: 1px solid #30363D', 'border: 1px solid #BBDEFB'),
    # 标签页
    ('border-bottom: 1px solid #21262D', 'border-bottom: 1px solid #BBDEFB'),
    ('background-color: #21262D', 'background-color: #E3F2FD'),
    # video_container
    ('background-color: #21262D', 'background-color: #FFFFFF'),
    # content_splitter (check for dark)
    ('background: #21262D', 'background: #BBDEFB'),
]

for old, new in replacements:
    c = c.replace(old, new)

import ast
ast.parse(c)
open('gui/main_window.py', 'w', encoding='utf-8').write(c)
count = sum(1 for old, _ in replacements if old in orig) - sum(1 for old, _ in replacements if old in c)
print(f'Applied {count} replacements. Syntax OK.')
