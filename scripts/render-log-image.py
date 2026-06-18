#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/noto/NotoSansMono-Regular.ttf",
        "/usr/share/fonts/TTF/JetBrainsMono-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
        "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: render-log-image.py <input.log> <output.png>", file=sys.stderr)
        return 2

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    text = src.read_text(errors="replace")
    lines = text.splitlines() or [""]

    font = load_font(18)
    padding_x = 26
    padding_y = 22
    line_gap = 8
    max_chars = min(max(len(line) for line in lines), 118)
    wrapped: list[str] = []
    for line in lines[:80]:
        if len(line) <= max_chars:
            wrapped.append(line)
            continue
        for i in range(0, len(line), max_chars):
            wrapped.append(line[i : i + max_chars])

    bbox = font.getbbox("M")
    char_width = bbox[2] - bbox[0]
    line_height = bbox[3] - bbox[1] + line_gap
    width = padding_x * 2 + max(820, char_width * max_chars)
    height = padding_y * 2 + max(1, len(wrapped)) * line_height

    image = Image.new("RGB", (width, height), (40, 44, 52))
    draw = ImageDraw.Draw(image)

    y = padding_y
    for line in wrapped:
        color = (228, 232, 239)
        if line.startswith("$ "):
            color = (143, 217, 205)
        elif "ERROR" in line or "Exception" in line:
            color = (244, 143, 134)
        elif "WARN" in line or "WARNING" in line:
            color = (236, 191, 120)
        draw.text((padding_x, y), line, fill=color, font=font)
        y += line_height

    dst.parent.mkdir(parents=True, exist_ok=True)
    image.save(dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
