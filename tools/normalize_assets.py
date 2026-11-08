#!/usr/bin/env python3
"""把 assets/raw 的立绘裁切、缩放到 frontend/public/assets。

像素风用 NEAREST 缩放，保持硬边；场景图单独按宽度缩放。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "assets" / "raw"
OUT = ROOT / "frontend" / "public" / "assets"
PORTRAIT_HEIGHT = 256
SCENE_WIDTH = 1024
PADDING = 0.08


def trim(image: Image.Image) -> Image.Image:
    """按背景色裁掉四周空白，并留一点边距。"""
    background = Image.new("RGB", image.size, image.getpixel((0, 0)))
    box = ImageChops.difference(image, background).getbbox()
    if box is None:
        return image

    left, top, right, bottom = box
    pad_x = int((right - left) * PADDING)
    pad_y = int((bottom - top) * PADDING)
    return image.crop(
        (
            max(0, left - pad_x),
            max(0, top - pad_y),
            min(image.width, right + pad_x),
            min(image.height, bottom + pad_y),
        )
    )


def main() -> int:
    """处理 raw 目录下的立绘与场景，输出到 public/assets。"""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "scenes").mkdir(exist_ok=True)

    count = 0
    for path in sorted(RAW.glob("*.png")):
        if path.name.startswith("_"):
            continue

        image = trim(Image.open(path).convert("RGB"))

        if path.name.startswith("scene"):
            ratio = SCENE_WIDTH / image.width
            size = (SCENE_WIDTH, round(image.height * ratio))
            target = OUT / "scenes" / path.name
        else:
            ratio = PORTRAIT_HEIGHT / image.height
            size = (max(1, round(image.width * ratio)), PORTRAIT_HEIGHT)
            target = OUT / path.name

        image.resize(size, Image.NEAREST).save(target, optimize=True)
        print(f"{path.name} -> {target.relative_to(ROOT).as_posix()} {size}")
        count += 1

    print(f"处理完成：{count} 个文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
