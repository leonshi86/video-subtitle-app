import struct, zlib, os

def create_png_arrow(filename, width=14, height=9, color=(50, 50, 50)):
    # PNG header
    sig = b'\x89PNG\r\n\x1a\n'
    # IHDR
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff
    ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
    # IDAT - draw a down arrow triangle
    raw = []
    for y in range(height):
        row = [0]  # filter byte
        for x in range(width):
            arrow_rows = height
            if y < arrow_rows:
                rel_y = y
                rel_h = arrow_rows
                max_w = width - 2
                w_at_row = int((rel_y / max(rel_h - 1, 1)) * max_w)
                w_at_row = max(w_at_row, 1)
                center = width // 2
                left = center - w_at_row // 2
                right = left + w_at_row
                if left <= x < right:
                    row.extend(color + (255,) )
                else:
                    row.extend([0, 0, 0, 0])
            else:
                row.extend([0, 0, 0, 0])
        raw.append(bytes(row))
    compressed = zlib.compress(b''.join(raw), 9)
    idat_crc = zlib.crc32(b'IDAT' + compressed) & 0xffffffff
    idat = struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc)
    iend_crc = zlib.crc32(b'IEND') & 0xffffffff
    iend = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'wb') as f:
        f.write(sig + ihdr + idat + iend)
    print(f'Created {filename}')

os.chdir(os.path.dirname(os.path.dirname(__file__)) or '.')
create_png_arrow('gui/assets/arrow_down.png', width=14, height=9, color=(50, 50, 50))
