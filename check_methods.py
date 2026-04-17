import ast
src = open('gui/main_window.py', encoding='utf-8').read()
tree = ast.parse(src)
methods = {}
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == 'MainWindow':
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods[item.name] = item.lineno

required = ['_poll_vlc_state', '_get_display_title', '_on_slider_click', 
            '_adjust_volume_up', '_adjust_volume_down', '_on_volume_slider_changed', 
            '_toggle_subtitle_display', '_on_vlc_state_changed', '_setup_media_player',
            '_on_vlc_state_changed']
for m in required:
    status = 'OK' if m in methods else 'MISSING'
    print(f'{m}: {status} (line {methods.get(m, "?")})')
print(f'Total methods: {len(methods)}')
print(f'Total lines: {len(src.splitlines())}')
