import ast, re

PATH = 'gui/main_window.py'
src = open(PATH, encoding='utf-8').read()
lines = src.split('\n')

def clean(line):
    # QMediaPlayer.PlaybackState.xxx
    line = line.replace('QMediaPlayer.PlaybackState.PlayingState', 'vlc.State.Playing')
    line = line.replace('QMediaPlayer.PlaybackState.PausedState', 'vlc.State.Paused')
    line = line.replace('QMediaPlayer.PlaybackState.StoppedState', 'vlc.State.Stopped')
    line = line.replace('QMediaPlayer.MediaStatus.', 'vlc.State.')
    line = line.replace('QMediaPlayer.Error', 'str')
    # media_player replacements
    line = line.replace('self.media_player.source().toLocalFile()', '(self._current_video_path or "")')
    line = line.replace('self.media_player.source().toString()', '(self._current_video_path or "")')
    line = line.replace('self.media_player.source().isValid()', 'self._vlc_player.get_media() is not None')
    line = line.replace('self.media_player.playbackState()', 'self._vlc_player.get_state()')
    line = line.replace('self.media_player.play()', 'self._vlc_player.play()')
    line = line.replace('self.media_player.pause()', 'self._vlc_player.pause()')
    line = line.replace('self.media_player.stop()', 'self._vlc_player.stop()')
    line = line.replace('self.media_player.setPosition(position)', 'self._vlc_player.set_time(position)')
    line = line.replace('self.media_player.duration()', 'self._vlc_player.get_length()')
    line = line.replace('self.media_player.setSource(media_source)', 'self._vlc_player.set_media(media)')
    # 删除 QMediaPlayer 初始化
    if 'self.media_player = QMediaPlayer()' in line: return ''
    if 'self.media_player.setAudioOutput' in line: return ''
    if 'self.media_player.setVideoOutput' in line: return ''
    if 'self.media_player.errorOccurred.connect' in line: return ''
    if 'self.media_player.positionChanged.connect' in line: return ''
    if 'self.media_player.durationChanged.connect' in line: return ''
    if 'self.media_player.playbackStateChanged.connect' in line: return ''
    if 'self.media_player.mediaStatusChanged.connect' in line: return ''
    # 颜色替换
    line = line.replace('#0D1117', '#FFFFFF')
    line = line.replace('#161B22', '#FFFFFF')
    line = line.replace('#1C2128', '#FFFFFF')
    line = line.replace('#21262D', '#FFFFFF')
    line = line.replace('#30363D', '#BBDEFB')
    line = line.replace('color: #E6EDF3', 'color: #1E3A5F')
    line = line.replace('color: #8B949E', 'color: #5D7A9C')
    line = line.replace('color: #6E7681', 'color: #5D7A9C')
    line = line.replace('background: #30363D', 'background: #E3F2FD')
    line = line.replace('background: #21262D', 'background: #E3F2FD')
    line = line.replace('border-bottom: 1px solid #21262D', 'border-bottom: 1px solid #BBDEFB')
    line = line.replace('background-color: #238636', 'background-color: #4CAF50')
    line = line.replace('border: 1px solid #30363D', 'border: 1px solid #BBDEFB')
    return line

cleaned = [clean(l) for l in lines]
# 去掉连续的空行
new_lines = []
for l in cleaned:
    if l.strip() == '' and new_lines and new_lines[-1].strip() == '':
        continue
    new_lines.append(l)

c = '\n'.join(new_lines)
try:
    ast.parse(c)
    print('Syntax OK')
    open(PATH, 'w', encoding='utf-8').write(c)
    print('Saved')
except SyntaxError as e:
    print(f'SYNTAX ERROR line {e.lineno}: {e.msg}')
    lines2 = c.split('\n')
    for k in range(max(0, e.lineno-3), min(len(lines2), e.lineno+3)):
        mark = '>>>' if k == e.lineno-1 else '   '
        print(f'{mark} {k+1}: {repr(lines2[k][:100])}')

# 残留检查
mp = re.findall(r'self\.media_player(?![\w_])', c)
qmp = re.findall(r'QMediaPlayer\.', c)
dark = re.findall(r'#0D1117|#161B22|#21262D', c)
print(f'media_player refs: {len(mp)}, QMediaPlayer: {len(qmp)}, dark: {len(dark)}')
if mp:
    for m in mp[:5]:
        idx = c.index(m)
        print(f'  ...{repr(c[max(0,idx-20):idx+30])}')
if qmp:
    for q in qmp[:5]:
        idx = c.index(q)
        print(f'  ...{repr(c[max(0,idx-20):idx+30])}')
if dark:
    for d in dark[:5]:
        idx = c.index(d)
        print(f'  ...{repr(c[max(0,idx-20):idx+30])}')
