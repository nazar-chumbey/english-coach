from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

TOP, BOTTOM = (0x7F, 0x8C, 0xF5), (0xB0, 0x7C, 0xF0)


def rounded(x: float, y: float, x0: float, y0: float, x1: float, y1: float, r: float) -> bool:
    cx, cy = min(max(x, x0 + r), x1 - r), min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def pixel(x: float, y: float) -> tuple[int, int, int, int] | None:
    if not rounded(x, y, 0.06, 0.06, 0.94, 0.94, 0.2):
        return None
    t = (x + y) / 2
    base = tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM))
    bubble = rounded(x, y, 0.2, 0.24, 0.8, 0.66, 0.14)
    tail = 0.3 <= x <= 0.44 and 0.6 <= y <= 0.78 and y - 0.6 <= (0.44 - x) * 1.3
    dot = any((x - cx) ** 2 + (y - 0.45) ** 2 <= 0.045 ** 2 for cx in (0.36, 0.5, 0.64))
    return (*(base if dot or not (bubble or tail) else (255, 255, 255)), 255)


def png(size: int) -> bytes:
    rows = []
    for j in range(size):
        row = bytearray(b"\0")
        for i in range(size):
            samples = [pixel((i + dx) / size, (j + dy) / size) for dx in (0.25, 0.75) for dy in (0.25, 0.75)]
            hits = [s for s in samples if s]
            rgb = [sum(s[k] for s in hits) // len(hits) if hits else 0 for k in range(3)]
            row += bytes([*rgb, 255 * len(hits) // 4])
        rows.append(bytes(row))
    chunk = lambda kind, body: struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    for target, size in ((root / "tools/icon.png", 1024), (root / "web/icon.png", 256)):
        target.write_bytes(png(size))
        print(target, file=sys.stderr)
