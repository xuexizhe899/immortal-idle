#!/usr/bin/env python3
"""把主城地形与建筑 sprite 量化成调色板 PNG，压小首屏体积。

地形从 assets/raw 重新量化，建筑用 chroma_key.py 的产物；两者都只量化一次。
建筑保留一个专用透明索引，避免把 alpha 展开成 RGBA 像素流。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "assets" / "raw"
ASSETS = ROOT / "frontend" / "public" / "assets"
TERRAIN_COLORS = 256
SPRITE_COLORS = 255  # 255 号索引留给透明
TRANSPARENT_INDEX = 255


def report(path: Path, before: int) -> None:
    """打印单张图的压缩结果。"""
    print(f"{path.name}: {before // 1024}K -> {path.stat().st_size // 1024}K")


def shrink_terrain() -> None:
    """从原图量化地形，输出为 P 模式 PNG。"""
    source = Image.open(RAW / "city_terrain.png").convert("RGB")
    target = ASSETS / "scenes" / "city_terrain.png"
    before = target.stat().st_size
    source.quantize(colors=TERRAIN_COLORS, method=Image.Quantize.FASTOCTREE).save(
        target, optimize=True
    )
    report(target, before)


def shrink_sprite(path: Path) -> None:
    """把 RGBA 建筑压成调色板图，透明像素指向专用索引。"""
    source = Image.open(path).convert("RGBA")
    before = path.stat().st_size

    quantized = source.convert("RGB").quantize(
        colors=SPRITE_COLORS, method=Image.Quantize.FASTOCTREE
    )
    alpha = source.getchannel("A").get_flattened_data()
    indices = [
        TRANSPARENT_INDEX if a == 0 else index
        for index, a in zip(quantized.get_flattened_data(), alpha)
    ]

    output = Image.new("P", source.size)
    palette = quantized.getpalette()
    output.putpalette(palette + [0, 0, 0] * (256 - len(palette) // 3))
    output.putdata(indices)
    # P 模式的 transparency 必须是「每个索引的 alpha 表」；传整数会被当成表长度
    alpha_table = bytearray([255] * 256)
    alpha_table[TRANSPARENT_INDEX] = 0
    output.save(path, optimize=True, transparency=bytes(alpha_table))
    report(path, before)


def main() -> None:
    """处理地形与全部建筑 sprite。"""
    shrink_terrain()
    for path in sorted((ASSETS / "buildings").glob("*.png")):
        shrink_sprite(path)


if __name__ == "__main__":
    main()
