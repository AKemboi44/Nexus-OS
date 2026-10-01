#!/usr/bin/env python3
"""Build Chrome Web Store-ready icon assets and a minimal extension ZIP."""

import json
import math
import struct
import zipfile
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ICON_DIR = ROOT / "icons"
DIST_DIR = ROOT / "dist"
ICON_SIZES = (16, 32, 48, 128)
PACKAGE_FILES = ("manifest.json", "popup.html", "popup.js", "auth.js")


def _inside_rounded_square(x, y, size, radius):
    nearest_x = min(max(x, radius), size - radius)
    nearest_y = min(max(y, radius), size - radius)
    return (x - nearest_x) ** 2 + (y - nearest_y) ** 2 <= radius**2


def _sample_icon(x, y, size):
    if not _inside_rounded_square(x, y, size, size * 0.22):
        return (0, 0, 0, 0)

    blend = min(1.0, max(0.0, (x + y) / (2 * size)))
    red = round(37 + (124 - 37) * blend)
    green = round(99 + (58 - 99) * blend)
    blue = round(235 + (237 - 235) * blend)

    def distance(px, py):
        return math.hypot(x - px * size, y - py * size)

    # Magnifier lens and its handle.
    lens_distance = distance(0.45, 0.43)
    if 0.185 * size <= lens_distance <= 0.245 * size:
        return (255, 255, 255, 255)
    if _distance_to_segment(x, y, 0.60 * size, 0.60 * size, 0.79 * size, 0.79 * size) <= 0.045 * size:
        return (255, 255, 255, 255)

    # Three connected evidence nodes inside the lens.
    nodes = ((0.37, 0.39), (0.49, 0.34), (0.51, 0.48))
    for first, second in ((nodes[0], nodes[1]), (nodes[0], nodes[2]), (nodes[1], nodes[2])):
        if _distance_to_segment(
            x, y, first[0] * size, first[1] * size, second[0] * size, second[1] * size
        ) <= 0.012 * size:
            return (225, 232, 255, 255)
    for node_x, node_y in nodes:
        if distance(node_x, node_y) <= 0.027 * size:
            return (255, 255, 255, 255)
    return (red, green, blue, 255)


def _distance_to_segment(x, y, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    denominator = dx * dx + dy * dy
    t = 0 if denominator == 0 else min(1, max(0, ((x - x1) * dx + (y - y1) * dy) / denominator))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def _png_chunk(chunk_type, data):
    content = chunk_type + data
    return struct.pack(">I", len(data)) + content + struct.pack(">I", zlib.crc32(content) & 0xFFFFFFFF)


def write_icon(path, size):
    scale = 4
    rows = []
    for y in range(size):
        row = bytearray((0,))
        for x in range(size):
            samples = [
                _sample_icon((x + sx / scale + 0.5 / scale), (y + sy / scale + 0.5 / scale), size)
                for sy in range(scale)
                for sx in range(scale)
            ]
            row.extend(round(sum(pixel[channel] for pixel in samples) / len(samples)) for channel in range(4))
        rows.append(bytes(row))
    raw = b"".join(rows)
    header = struct.pack(">2I5B", size, size, 8, 6, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", header) + _png_chunk(b"IDAT", zlib.compress(raw, 9)) + _png_chunk(b"IEND", b""))


def build_package():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    for size in ICON_SIZES:
        icon = ICON_DIR / f"icon-{size}.png"
        if not icon.is_file():
            raise FileNotFoundError(f"Missing required extension icon: {icon}")
    package = DIST_DIR / f"nexus-research-ai-{manifest['version']}.zip"
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in PACKAGE_FILES:
            archive.write(ROOT / relative, relative)
        for size in ICON_SIZES:
            relative = f"icons/icon-{size}.png"
            archive.write(ROOT / relative, relative)
    return package


if __name__ == "__main__":
    for icon_size in ICON_SIZES:
        write_icon(ICON_DIR / f"icon-{icon_size}.png", icon_size)
    print(f"Built {build_package()}")
