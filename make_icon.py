"""Draws Jarvis's icon (a glowing arc-reactor ring): jarvis.ico for Windows shortcuts and jarvis.png for Linux
app menus. The installers run this; you can also run it yourself: python make_icon.py"""

import struct
import zlib
from pathlib import Path

import numpy as np


def draw(size: int) -> np.ndarray:
    """RGBA image of a cyan ring with a bright core."""
    y, x = np.mgrid[0:size, 0:size] + 0.5
    r = np.hypot(x - size / 2, y - size / 2) / (size / 2)  # 0 at the centre, 1 at the edge
    ring = np.exp(-((r - 0.72) / 0.09) ** 2)               # main ring
    glow = np.exp(-((r - 0.72) / 0.22) ** 2) * 0.45         # soft halo around it
    core = np.exp(-(r / 0.28) ** 2)                         # bright centre
    alpha = np.clip(ring + glow + core, 0, 1) * (r < 0.98)
    white = np.clip(core * 1.2 + ring * 0.35, 0, 1)         # hottest parts fade to white
    rgb = np.stack([0.15 + 0.85 * white, 0.75 + 0.25 * white, np.ones_like(r)], axis=-1)
    return (np.dstack([rgb, alpha]) * 255).astype(np.uint8)


def ico_bytes(sizes=(16, 32, 48, 64, 128, 256)) -> bytes:
    """A Windows .ico file holding 32-bit bitmaps at several sizes."""
    images = []
    for s in sizes:
        rgba = draw(s)
        bgra = rgba[::-1, :, [2, 1, 0, 3]].tobytes()  # bitmaps are stored bottom-up, as BGRA
        mask = b"\x00" * (((s + 31) // 32) * 4 * s)    # all-visible AND mask (alpha does the real work)
        header = struct.pack("<IiiHHIIiiII", 40, s, s * 2, 1, 32, 0, len(bgra) + len(mask), 0, 0, 0, 0)
        images.append((s, header + bgra + mask))
    out = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    for s, data in images:
        out += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return out + b"".join(data for _, data in images)


def png_bytes(size: int = 256) -> bytes:
    rgba = draw(size)
    raw = b"".join(b"\x00" + rgba[y].tobytes() for y in range(size))  # each row starts with filter type 0

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    here = Path(__file__).parent
    (here / "jarvis.ico").write_bytes(ico_bytes())
    (here / "jarvis.png").write_bytes(png_bytes())
    print(f"Wrote {here / 'jarvis.ico'} and {here / 'jarvis.png'}")
