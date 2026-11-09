#!/usr/bin/env python3
"""把洋红底建筑 sprite 抠成透明 PNG，并按宽度缩放到前端可用尺寸。

只处理 assets/raw/sprite_*.png；输出到 frontend/public/assets/buildings/。
洋红判定放宽到 R/B 高、G 低的粉紫区间；抠完对 alpha 做 1px 腐蚀去色边。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "assets" / "raw"
OUT = ROOT / "frontend" / "public" / "assets" / "buildings"
TARGET_WIDTH = 512


def is_magenta(r: int, g: int, b: int) -> bool:
    return r > 150 and b > 150 and g < 110 and abs(r - b) < 90


def key_out(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            if is_magenta(r, g, b):
                pixels[x, y] = (r, g, b, 0)
    # 腐蚀 1px：把贴在透明边缘的粉紫色边一并吃掉
    rgba.putalpha(rgba.getchannel("A").filter(ImageFilter.MinFilter(3)))
    box = rgba.getbbox()
    if box:
        rgba = rgba.crop(box)
    return rgba


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in sorted(RAW.glob("sprite_*.png")):
        image = key_out(Image.open(path))
        ratio = TARGET_WIDTH / image.width
        size = (TARGET_WIDTH, max(1, round(image.height * ratio)))
        target = OUT / path.name
        image.resize(size, Image.NEAREST).save(target, optimize=True)
        print(f"{path.name} -> {target.relative_to(ROOT).as_posix()} {size}")
        count += 1
    print(f"抠图完成：{count} 个文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())