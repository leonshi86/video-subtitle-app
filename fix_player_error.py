import ast
c = open('gui/main_window.py', encoding='utf-8').read()
lines = c.split('\n')

# 找到并修复 _on_player_error
for i, l in enumerate(lines):
    if '@Slot(QMediaPlayer.Error, str)' in l:
        end = i + 1
        while end < len(lines):
            if lines[end].startswith('    # \u2500\u2500') and '\u5bfc\u51fa' in lines[end]:
                break
            end += 1
        lines = lines[:i] + [
            '    def _on_player_error(self, msg: str = "") -> None:',
            '        logger.error("播放器错误: %s", msg)',
            ''
        ] + lines[end:]
        print(f'Fixed _on_player_error at line {i+1}')
        break

# 找到并修复 _on_media_status_changed
for i, l in enumerate(lines):
    if '@Slot("QMediaPlayer::MediaStatus")' in l:
        end = i + 1
        while end < len(lines):
            if lines[end].startswith('    def ') and '_on_media' not in lines[end]:
                break
            end += 1
        lines = lines[:i] + [
            '    def _on_media_status_changed(self, status) -> None:',
            '        pass',
            ''
        ] + lines[end:]
        print(f'Fixed _on_media_status_changed at line {i+1}')
        break

c = '\n'.join(lines)
ast.parse(c)
open('gui/main_window.py', 'w', encoding='utf-8').write(c)
print('Done')
