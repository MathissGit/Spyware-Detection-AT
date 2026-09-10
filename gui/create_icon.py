"""Génère une icône PNG de l'application sans dépendance externe.

Cette implémentation écrit directement les octets PNG (format de base,
sans filtres ni compression externe) afin de fonctionner sur n'importe quel
système disposant uniquement de Python. L'icône est utilisée par l'IHM
(sidebar, écran d'accueil).
"""
import os
import zlib
import struct

COLORS = {
    "PRIMARY": (29, 191, 238),      # #1dbfee
    "WARNING": (255, 236, 1),       # #ffec01
    "SECONDARY": (206, 191, 255),   # #cebfff
    "SUCCESS": (19, 211, 170),      # #13d3aa
    "DANGER": (255, 1, 11),         # #ff010b
    "BG_LIGHT": (254, 254, 254),    # #fefefe
    "BG_DARK": (0, 0, 0),           # #000000
}


def _encode_png(width, height, pixels):
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        c += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return c

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw.extend(pixels[y][x])
    idat = zlib.compress(bytes(raw), 9)
    return (sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b""))


def draw_icon(size=512):
    """Dessine un bouclier de détection spyware sur fond primaire."""
    pixels = [[COLORS["PRIMARY"] for _ in range(size)] for _ in range(size)]
    bg_dark = COLORS["BG_DARK"]
    warning = COLORS["WARNING"]
    success = COLORS["SUCCESS"]
    light = COLORS["BG_LIGHT"]

    margin = int(size * 0.15)
    cx = size // 2
    top = int(size * 0.18)
    bottom = size - margin

    shield_bottom_y = int(top + (bottom - top) * 0.72)

    def in_shield(x, y):
        if y < top or y > shield_bottom_y:
            return False
        t = (y - top) / (shield_bottom_y - top) if shield_bottom_y != top else 0
        half = margin + t * 0.55 * (size - 2 * margin)
        center_shift = (size / 2 - margin) * t * 0.0
        left = cx - half
        right = cx + half
        return left <= x <= right

    def between(x, a, b):
        return a <= x <= b

    bar_top = int(top + (shield_bottom_y - top) * 0.28)
    bar_bottom = int(bar_top + size * 0.06)
    mid_y = int((bottom - margin) * 0.5)

    for y in range(size):
        for x in range(size):
            if in_shield(x, y):
                pixels[y][x] = bg_dark
                if between(y, bar_top, bar_bottom):
                    pixels[y][x] = warning
                elif y >= mid_y:
                    if between(x, cx - size * 0.05, cx + size * 0.05):
                        pixels[y][x] = success

    return pixels


def write_icon(path, size=512):
    pixels = draw_icon(size)
    data = _encode_png(size, size, pixels)
    with open(path, "wb") as f:
        f.write(data)
    return path


def ensure_icon(base_dir, size=512):
    icon_png = os.path.join(base_dir, "icon.png")
    if os.path.exists(icon_png):
        return icon_png
    try:
        write_icon(icon_png, size)
        return icon_png
    except Exception:
        return None


if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    icon = ensure_icon(base)
    print("ICON_OK", icon if icon else "UNAVAILABLE")
