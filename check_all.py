import ast
src = open('gui/main_window.py', encoding='utf-8').read()
ast.parse(src)
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == 'MainWindow':
        methods = {item.name: item.lineno for item in node.body if isinstance(item, ast.FunctionDef)}
        required = ['_poll_vlc_state', '_get_display_title', '_on_slider_click',
                    '_adjust_volume_up', '_adjust_volume_down', '_on_volume_slider_changed',
                    '_toggle_subtitle_display', '_on_vlc_state_changed', '_setup_media_player',
                    '_setup_ui']
        for m in required:
            status = 'OK' if m in methods else 'MISSING'
            line = methods.get(m, '?')
            print(m + ': ' + status + ' (line ' + str(line) + ')')
        break
print('Lines: ' + str(len(src.splitlines())))
