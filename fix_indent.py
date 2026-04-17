import ast
c = open('gui/main_window.py', encoding='utf-8').read()

# 修复缩进问题：找到无缩进的 def 并添加4空格缩进
lines = c.split('\n')
fixed = []
i = 0
while i < len(lines):
    l = lines[i]
    # 检测无缩进的 def（不在 class 行，且 def 前没有缩进）
    if l.startswith('def _poll_vlc_state'):
        # 这整块插入的方法都没缩进，需要加缩进
        indent = '    '
        block_start = i
        # 找到方法块的结束（下一个 def 或 class 开始）
        block_end = i + 1
        while block_end < len(lines):
            if lines[block_end] and not lines[block_end].startswith('        ') and (lines[block_end].startswith('def ') or lines[block_end].startswith('class ')):
                break
            block_end += 1
        # 给整个块加缩进
        for j in range(block_start, block_end):
            if lines[j] and not lines[j].startswith('    def ') and not lines[j].startswith('    #'):
                lines[j] = '    ' + lines[j]
        print(f'Fixed indentation for methods block at line {i+1}')
    i += 1

c = '\n'.join(lines)
ast.parse(c)
open('gui/main_window.py', 'w', encoding='utf-8').write(c)
print('Done')
