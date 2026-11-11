#!/usr/bin/env python3
"""把 assets/raw 的立绘裁切、缩放到 frontend/public/assets。

像素风用 NEAREST 缩放，保持硬边；场景图单独按宽度缩放。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops

from chroma_key import key_out

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "assets" / "raw"
OUT = ROOT / "frontend" / "public" / "assets"
PORTRAIT_HEIGHT = 256
SCENE_WIDTH = 1024
PADDING = 0.08


def trim(image: Image.Image) -> Image.Image:
    """按背景色裁掉四周空白，并留一点边距。"""
    if image.mode == "RGBA" and image.getchannel("A").getextrema()[0] < 255:
        box = image.getchannel("A").getbbox()
    else:
        sample = image.convert("RGB")
        background = Image.new("RGB", image.size, sample.getpixel((0, 0)))
        box = ImageChops.difference(sample, background).getbbox()
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=RAW)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    parser.add_argument("--portrait-height", type=int, default=PORTRAIT_HEIGHT)
    parser.add_argument("--scene-width", type=int, default=SCENE_WIDTH)
    parser.add_argument("--scene-colors", type=int, default=0, help="optional palette compression, 2..256 colors")
    parser.add_argument("--chroma-key", action="store_true", help="remove magenta from portraits only")
    parser.add_argument("--flat-scenes", action="store_true", help="save scenes directly beside portraits")
    args = parser.parse_args()
    if args.portrait_height < 1 or args.scene_width < 1:
        parser.error("output dimensions must be positive")
    if args.scene_colors and not 2 <= args.scene_colors <= 256:
        parser.error("--scene-colors must be 0 or between 2 and 256")
    output = args.output_dir.resolve()
    if not output.is_relative_to(ROOT.resolve()):
        parser.error("output directory must stay inside the repository")
    output.mkdir(parents=True, exist_ok=True)
    scene_output = output if args.flat_scenes else output / "scenes"
    scene_output.mkdir(exist_ok=True)

    count = 0
    for path in sorted(args.input_dir.glob("*.png")):
        if path.name.startswith("_"):
            continue

        if path.name.startswith("scene"):
            image = Image.open(path).convert("RGB")
            ratio = args.scene_width / image.width
            size = (args.scene_width, max(1, round(image.height * ratio)))
            target = scene_output / path.name
        else:
            image = Image.open(path).convert("RGBA")
            if args.chroma_key and image.getchannel("A").getextrema()[0] == 255:
                image = key_out(image)
            image = trim(image)
            ratio = args.portrait_height / image.height
            size = (max(1, round(image.width * ratio)), args.portrait_height)
            target = output / path.name

        result = image.resize(size, Image.NEAREST)
        if path.name.startswith("scene") and args.scene_colors:
            result = result.quantize(colors=args.scene_colors, method=Image.Quantize.FASTOCTREE)
        result.save(target, optimize=True)
        print(f"{path.name} -> {target.relative_to(ROOT).as_posix()} {size}")
        count += 1

    print(f"处理完成：{count} 个文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
