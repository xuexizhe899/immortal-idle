#!/usr/bin/env python3
"""本地生成道具图标。

读取 config/recipes 与 config/materials 中的真实 ID，用纯 Python 标准库
绘制 64×64 像素风 SVG，输出到 frontend/public/assets/items/。

运行：
    python tools/generate_item_icons.py

重复运行结果完全一致；只写入本脚本负责的 18 张图标与 index.json，
不会清空或改动输出目录中的其他文件。
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DEFAULT_OUTPUT = ROOT / "frontend" / "public" / "assets" / "items"

# 与现有立绘统一的青绿、象牙白、暖木与克制金色
INK = "#22342C"
INK_DEEP = "#16241F"
JADE_DEEP = "#3F7359"
JADE = "#5E9B77"
JADE_LIGHT = "#8CC4A2"
JADE_PALE = "#CFE8D8"
IVORY = "#F2EAD3"
IVORY_DEEP = "#DCCFB0"
IVORY_SHADOW = "#BFAF8C"
WOOD_DEEP = "#6E4528"
WOOD = "#9A6238"
WOOD_LIGHT = "#C58A53"
GOLD_DEEP = "#A78132"
GOLD = "#C9A24B"
GOLD_LIGHT = "#E8D08A"
IRON_DEEP = "#46565B"
IRON = "#66797E"
IRON_LIGHT = "#93A6AA"
IRON_PALE = "#C9D6D9"
CRYSTAL_DEEP = "#2C6B6B"
CRYSTAL = "#4E9F97"
CRYSTAL_LIGHT = "#86CFC4"
CRYSTAL_PALE = "#C6EDE5"
BONE_DEEP = "#A9946E"
BONE = "#D8C9A6"
BONE_LIGHT = "#EFE5CB"
LINGZHI_DEEP = "#7E3A31"
LINGZHI = "#B45743"
LINGZHI_LIGHT = "#D98A68"
PAPER = "#EFE3C6"
RED = "#A9473B"
SPIRIT_DEEP = "#3D6F8F"
SPIRIT = "#5E93B5"
SPIRIT_LIGHT = "#9CC6DE"
SPIRIT_PALE = "#D3E8F5"


class IconError(RuntimeError):
    """配置与绘图不一致时抛出，避免静默生成缺图。"""


def rect(
    x: int, y: int, w: int, h: int, fill: str,
    *, stroke: str | None = INK, width: int = 2, rx: int = 0,
) -> str:
    """输出一个像素对齐的矩形。"""
    attrs = f'x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"'
    if rx:
        attrs += f' rx="{rx}"'
    if stroke:
        attrs += f' stroke="{stroke}" stroke-width="{width}"'
    return f"<rect {attrs}/>"


def poly(
    points: Iterable[tuple[int, int]], fill: str,
    *, stroke: str | None = INK, width: int = 2,
) -> str:
    """输出一个像素对齐的多边形。"""
    value = " ".join(f"{x},{y}" for x, y in points)
    attrs = f'points="{value}" fill="{fill}"'
    if stroke:
        attrs += f' stroke="{stroke}" stroke-width="{width}"'
    return f"<polygon {attrs}/>"


def circle(
    cx: int, cy: int, r: int, fill: str,
    *, stroke: str | None = INK, width: int = 2,
) -> str:
    """输出一个圆形；根节点关闭抗锯齿后呈阶梯像素边。"""
    attrs = f'cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"'
    if stroke:
        attrs += f' stroke="{stroke}" stroke-width="{width}"'
    return f"<circle {attrs}/>"


def art_qing_feng_jian() -> list[str]:
    """青锋剑：直立剑身、金色护手、暖木握柄与剑穗。"""
    return [
        poly([(32, 4), (38, 15), (37, 41), (27, 41), (26, 15)], JADE),
        poly([(31, 9), (34, 16), (33, 39), (31, 39)], JADE_PALE, stroke=None),
        poly([(35, 18), (36, 20), (35, 39), (34, 39)], JADE_DEEP, stroke=None),
        rect(30, 18, 4, 3, GOLD, stroke=None),
        rect(20, 41, 24, 5, GOLD),
        rect(22, 42, 20, 2, GOLD_LIGHT, stroke=None),
        rect(29, 46, 6, 11, WOOD),
        rect(29, 49, 6, 2, GOLD_DEEP, stroke=None),
        rect(29, 53, 6, 2, GOLD_DEEP, stroke=None),
        rect(26, 57, 12, 4, GOLD),
        rect(43, 44, 2, 9, RED, stroke=None),
        rect(42, 52, 4, 3, GOLD, stroke=None),
    ]


def art_liao_shang_dan() -> list[str]:
    """疗伤丹：双球葫芦形丹体、金色束带与疗愈纹。"""
    return [
        circle(32, 44, 14, INK, stroke=None),
        circle(32, 24, 9, INK, stroke=None),
        rect(27, 27, 10, 17, INK, stroke=None),
        circle(32, 44, 12, IVORY, stroke=None),
        circle(32, 24, 7, IVORY, stroke=None),
        rect(29, 29, 6, 13, IVORY, stroke=None),
        circle(27, 39, 4, JADE_PALE, stroke=None),
        rect(26, 20, 4, 3, JADE_PALE, stroke=None),
        rect(24, 34, 16, 4, GOLD, stroke=None),
        rect(24, 37, 16, 1, GOLD_DEEP, stroke=None),
        rect(30, 40, 4, 10, JADE_DEEP, stroke=None),
        rect(26, 44, 12, 4, JADE_DEEP, stroke=None),
        rect(29, 12, 6, 5, WOOD),
        rect(31, 9, 2, 4, WOOD_DEEP, stroke=None),
        rect(25, 56, 14, 2, IVORY_SHADOW, stroke=None),
    ]


def art_ling_cao() -> list[str]:
    """灵草：深浅错落的三丛草叶、暖木根须与顶端小白花。"""
    return [
        poly([(30, 52), (23, 42), (16, 28), (18, 24), (26, 34), (31, 46)], JADE_DEEP),
        poly([(34, 52), (41, 40), (48, 26), (46, 22), (38, 32), (33, 46)], JADE_DEEP),
        poly([(28, 52), (20, 48), (14, 40), (16, 37), (24, 44), (30, 49)], JADE),
        poly([(36, 52), (44, 48), (50, 42), (48, 39), (40, 44), (34, 49)], JADE),
        poly([(32, 53), (29, 40), (30, 18), (32, 11), (34, 18), (35, 40)], JADE),
        poly([(31, 20), (32, 13), (33, 20), (32, 44)], JADE_PALE, stroke=None),
        rect(27, 52, 10, 4, WOOD),
        rect(30, 56, 4, 5, WOOD_DEEP),
        rect(23, 58, 6, 2, WOOD_DEEP, stroke=None),
        rect(35, 58, 6, 2, WOOD_DEEP, stroke=None),
        circle(32, 7, 3, IVORY),
        circle(28, 10, 3, IVORY),
        circle(36, 10, 3, IVORY),
        circle(32, 13, 3, IVORY),
        circle(32, 10, 2, GOLD, stroke=None),
    ]


def art_han_tie() -> list[str]:
    """寒铁：棱角矿块、左上方亮面与冰裂纹。"""
    return [
        poly([(14, 46), (20, 30), (32, 22), (44, 24), (52, 36), (50, 50), (40, 56), (24, 54)], IRON),
        poly([(17, 45), (23, 32), (33, 26), (36, 31), (28, 41), (22, 47)], IRON_LIGHT, stroke=None),
        poly([(36, 31), (43, 28), (49, 37), (47, 48), (39, 44), (34, 40)], IRON_DEEP, stroke=None),
        poly([(30, 24), (34, 17), (38, 24), (35, 28)], IRON_PALE),
        poly([(42, 26), (45, 20), (48, 27), (45, 31)], IRON_PALE),
        rect(27, 34, 10, 2, IRON_PALE, stroke=None),
        rect(33, 38, 9, 2, IRON_PALE, stroke=None),
        rect(25, 44, 6, 2, IRON_DEEP, stroke=None),
    ]


def art_yun_mu() -> list[str]:
    """云母：三层错叠矿片，浅色层理与金色接缝。"""
    return [
        poly([(12, 42), (40, 38), (54, 44), (50, 54), (20, 56)], BONE),
        poly([(15, 43), (39, 40), (49, 45), (46, 50), (21, 52)], BONE_LIGHT, stroke=None),
        poly([(18, 32), (44, 28), (50, 34), (46, 42), (16, 44)], BONE),
        poly([(21, 33), (43, 30), (47, 34), (44, 39), (19, 41)], IVORY, stroke=None),
        poly([(24, 22), (44, 18), (48, 24), (44, 32), (22, 32)], BONE),
        poly([(27, 24), (43, 21), (45, 24), (42, 29), (25, 29)], IVORY, stroke=None),
        poly([(27, 24), (43, 21), (44, 23), (28, 26)], GOLD_LIGHT, stroke=None),
        poly([(21, 33), (43, 30), (44, 32), (22, 35)], GOLD_LIGHT, stroke=None),
        poly([(15, 43), (39, 40), (40, 42), (16, 45)], GOLD_LIGHT, stroke=None),
    ]


def art_jiao_gu() -> list[str]:
    """蛟骨：弯曲骨条、两端骨节与金玉束带。"""
    return [
        poly(
            [(18, 54), (15, 44), (19, 30), (28, 18), (38, 10), (44, 13),
             (43, 18), (36, 26), (30, 36), (28, 48), (30, 56)],
            BONE,
        ),
        poly(
            [(20, 50), (18, 42), (22, 31), (30, 20), (38, 14),
             (34, 20), (28, 30), (24, 40), (24, 50)],
            BONE_LIGHT, stroke=None,
        ),
        poly(
            [(36, 22), (40, 17), (41, 20), (36, 28), (31, 36),
             (30, 44), (28, 46), (30, 34)],
            BONE_DEEP, stroke=None,
        ),
        rect(25, 38, 8, 3, GOLD, stroke=None),
        rect(29, 28, 6, 3, JADE_DEEP, stroke=None),
        rect(26, 32, 2, 6, BONE_DEEP, stroke=None),
        rect(32, 24, 2, 5, BONE_DEEP, stroke=None),
        circle(21, 48, 4, BONE),
        circle(41, 13, 4, BONE),
        rect(24, 49, 4, 2, BONE_LIGHT, stroke=None),
        rect(39, 11, 3, 2, BONE_LIGHT, stroke=None),
    ]


def art_jiu_ye() -> list[str]:
    """九叶灵芝：扇形菌盖、层状金边、暖木菌柄与侧叶。"""
    return [
        poly([(29, 54), (35, 54), (36, 38), (32, 32), (28, 38)], WOOD_LIGHT),
        poly([(30, 52), (33, 52), (34, 38), (32, 35), (30, 38)], IVORY, stroke=None),
        poly(
            [(14, 32), (18, 22), (28, 16), (40, 16), (50, 24), (52, 32),
             (44, 36), (32, 34), (20, 36)],
            LINGZHI,
        ),
        poly(
            [(18, 30), (21, 23), (29, 18), (39, 18), (47, 25), (48, 30),
             (42, 33), (32, 31), (21, 33)],
            LINGZHI_LIGHT, stroke=None,
        ),
        poly([(16, 31), (48, 31), (45, 35), (21, 35)], GOLD_LIGHT, stroke=None),
        poly([(22, 28), (27, 22), (39, 22), (45, 28), (40, 25), (28, 25)], GOLD, stroke=None),
        poly([(28, 31), (32, 27), (36, 31), (32, 29)], LINGZHI_DEEP, stroke=None),
        circle(24, 26, 1, GOLD_LIGHT, stroke=None),
        circle(40, 26, 1, GOLD_LIGHT, stroke=None),
        poly([(36, 44), (44, 36), (48, 40), (40, 48)], JADE),
        rect(35, 45, 8, 2, JADE_DEEP, stroke=None),
    ]


def art_xuan_jing() -> list[str]:
    """玄晶：三棱晶簇、深青晶面与左上高光。"""
    return [
        poly([(16, 52), (24, 44), (40, 44), (50, 52), (44, 56), (22, 56)], IRON_DEEP),
        poly([(19, 52), (25, 46), (39, 46), (47, 52), (42, 54), (24, 54)], IRON, stroke=None),
        poly([(20, 24), (24, 18), (28, 24), (27, 42), (21, 46), (18, 40)], CRYSTAL),
        poly([(22, 25), (24, 21), (26, 25), (25, 41), (22, 43)], CRYSTAL_PALE, stroke=None),
        poly([(30, 14), (36, 8), (42, 16), (40, 42), (32, 48), (28, 40), (28, 20)], CRYSTAL_DEEP),
        poly([(31, 16), (34, 12), (35, 42), (31, 44)], CRYSTAL_LIGHT, stroke=None),
        poly([(36, 17), (39, 14), (39, 40), (36, 42)], CRYSTAL, stroke=None),
        poly([(44, 20), (48, 14), (52, 22), (50, 42), (45, 46), (42, 38)], CRYSTAL_DEEP),
        poly([(45, 21), (48, 18), (49, 24), (48, 40), (46, 42)], CRYSTAL_LIGHT, stroke=None),
    ]


def art_gu_ti_dan() -> list[str]:
    """固元丹：八棱丹体、方形丹纹与四角镇压纹。"""
    return [
        poly([(24, 16), (40, 16), (48, 24), (48, 40), (40, 48), (24, 48), (16, 40), (16, 24)], IVORY),
        poly([(25, 19), (39, 19), (45, 25), (45, 39), (39, 45), (25, 45), (19, 39), (19, 25)], IVORY_DEEP, stroke=None),
        rect(26, 30, 12, 12, GOLD),
        rect(29, 33, 6, 6, JADE_DEEP, stroke=None),
        rect(23, 26, 4, 4, JADE, stroke=None),
        rect(37, 26, 4, 4, JADE, stroke=None),
        rect(23, 38, 4, 4, JADE, stroke=None),
        rect(37, 38, 4, 4, JADE, stroke=None),
        rect(21, 21, 8, 2, IVORY, stroke=None),
        rect(22, 49, 20, 3, GOLD_DEEP, stroke=None),
    ]


def art_hui_ling_dan() -> list[str]:
    """回灵丹：圆形丹体、螺旋丹纹与侧生灵叶。"""
    return [
        circle(32, 34, 17, JADE_LIGHT),
        circle(32, 34, 13, JADE_PALE, stroke=None),
        rect(30, 22, 4, 2, JADE_DEEP, stroke=None),
        rect(38, 24, 2, 8, JADE_DEEP, stroke=None),
        rect(32, 32, 7, 2, JADE_DEEP, stroke=None),
        rect(28, 30, 2, 5, JADE_DEEP, stroke=None),
        rect(30, 28, 4, 2, JADE_DEEP, stroke=None),
        rect(23, 30, 3, 2, JADE, stroke=None),
        rect(22, 24, 5, 3, IVORY, stroke=None),
        poly([(39, 14), (48, 9), (46, 18), (40, 21)], JADE),
        rect(41, 15, 5, 2, JADE_DEEP, stroke=None),
        rect(24, 50, 16, 3, GOLD_DEEP, stroke=None),
    ]


def art_ju_qi_dan() -> list[str]:
    """聚气丹：同心丹纹、下沉丹体与上升气团。"""
    return [
        poly([(19, 23), (17, 18), (20, 13), (25, 15), (27, 20), (24, 24)], SPIRIT_LIGHT),
        poly([(38, 20), (37, 15), (41, 11), (46, 14), (46, 19), (42, 22)], SPIRIT_LIGHT),
        circle(32, 38, 15, SPIRIT_LIGHT),
        circle(32, 38, 11, SPIRIT_PALE, stroke=None),
        circle(32, 38, 7, SPIRIT_LIGHT, stroke=SPIRIT_DEEP, width=2),
        circle(32, 38, 3, SPIRIT_DEEP, stroke=None),
        rect(23, 31, 4, 3, IVORY, stroke=None),
        rect(36, 20, 2, 2, GOLD, stroke=None),
        rect(22, 56, 20, 3, SPIRIT_DEEP, stroke=None),
    ]


def art_po_jing_dan() -> list[str]:
    """破境丹：六棱晶丹、贯穿裂纹与四散金色碎光。"""
    return [
        poly([(32, 12), (46, 20), (46, 40), (32, 50), (18, 40), (18, 20)], CRYSTAL_LIGHT),
        poly([(31, 16), (31, 46), (21, 38), (21, 22)], CRYSTAL_PALE, stroke=None),
        poly([(33, 16), (43, 22), (43, 38), (33, 46)], CRYSTAL, stroke=None),
        poly(
            [(31, 12), (34, 20), (31, 27), (34, 35), (31, 44),
             (33, 46), (36, 35), (33, 28), (36, 20), (33, 12)],
            INK, stroke=None,
        ),
        poly([(12, 14), (18, 10), (19, 17), (14, 20)], GOLD),
        poly([(47, 13), (53, 10), (54, 18), (49, 20)], GOLD),
        circle(50, 30, 3, GOLD),
        circle(15, 28, 2, GOLD),
        rect(22, 50, 20, 3, CRYSTAL_DEEP, stroke=None),
    ]


def art_yang_shen_dan() -> list[str]:
    """养神丹：横置眼形丹体、金色瞳纹与莲座。"""
    return [
        poly([(18, 42), (24, 54), (32, 46)], JADE),
        poly([(32, 46), (40, 54), (46, 42)], JADE_DEEP),
        poly([(26, 44), (32, 56), (38, 44)], JADE_LIGHT),
        poly(
            [(12, 33), (22, 23), (32, 21), (42, 23), (52, 33),
             (42, 43), (32, 45), (22, 43)],
            IVORY,
        ),
        poly(
            [(16, 33), (24, 26), (32, 25), (40, 26), (48, 33),
             (40, 40), (32, 41), (24, 40)],
            SPIRIT_LIGHT, stroke=None,
        ),
        circle(32, 33, 7, GOLD),
        circle(32, 33, 4, INK_DEEP, stroke=None),
        circle(30, 31, 1, IVORY, stroke=None),
        rect(20, 45, 24, 2, GOLD_DEEP, stroke=None),
    ]


def art_hu_xin_jing() -> list[str]:
    """护心镜：圆形铜镜、放射镜纹、中心镜钮与红穗。"""
    return [
        circle(32, 34, 18, GOLD_DEEP),
        circle(32, 34, 15, GOLD_LIGHT, stroke=None),
        circle(32, 34, 11, IVORY),
        circle(32, 34, 6, GOLD),
        circle(30, 32, 2, IVORY, stroke=None),
        rect(31, 16, 2, 5, GOLD_DEEP, stroke=None),
        rect(31, 47, 2, 5, GOLD_DEEP, stroke=None),
        rect(14, 33, 5, 2, GOLD_DEEP, stroke=None),
        rect(45, 33, 5, 2, GOLD_DEEP, stroke=None),
        rect(19, 22, 5, 2, GOLD_DEEP, stroke=None),
        rect(40, 22, 5, 2, GOLD_DEEP, stroke=None),
        rect(19, 45, 5, 2, GOLD_DEEP, stroke=None),
        rect(40, 45, 5, 2, GOLD_DEEP, stroke=None),
        circle(32, 12, 3, GOLD),
        rect(31, 50, 2, 6, RED, stroke=None),
        rect(29, 56, 6, 3, GOLD, stroke=None),
    ]


def art_ju_ling_pei() -> list[str]:
    """聚灵佩：玉牌、金冠、云纹与垂穗。"""
    return [
        poly([(24, 14), (40, 14), (44, 20), (44, 42), (32, 54), (20, 42), (20, 20)], JADE_LIGHT),
        poly([(26, 17), (38, 17), (41, 21), (41, 41), (32, 50), (23, 41), (23, 21)], JADE_PALE, stroke=None),
        poly([(28, 24), (36, 24), (36, 32), (32, 36), (28, 32)], JADE_DEEP, stroke=None),
        rect(30, 28, 4, 2, GOLD_LIGHT, stroke=None),
        rect(25, 38, 4, 2, GOLD, stroke=None),
        rect(35, 38, 4, 2, GOLD, stroke=None),
        rect(27, 10, 10, 5, GOLD),
        rect(30, 5, 4, 3, GOLD_DEEP, stroke=None),
        rect(31, 52, 2, 8, RED, stroke=None),
        rect(29, 58, 6, 3, GOLD, stroke=None),
    ]


def art_liu_yun_xue() -> list[str]:
    """流云靴：高筒靴形、云头纹与金色鞋底。"""
    return [
        poly(
            [(18, 16), (30, 16), (32, 34), (38, 38), (50, 40), (52, 48),
             (48, 54), (18, 54), (16, 44), (16, 30)],
            IVORY,
        ),
        poly(
            [(20, 19), (28, 19), (30, 35), (37, 39), (48, 41), (49, 47),
             (45, 51), (20, 51), (19, 43), (19, 31)],
            JADE_PALE, stroke=None,
        ),
        rect(16, 16, 16, 4, GOLD),
        rect(18, 52, 32, 3, GOLD_DEEP, stroke=None),
        poly([(20, 26), (26, 22), (30, 26), (26, 30)], JADE, stroke=None),
        poly([(22, 32), (28, 28), (32, 32), (28, 36)], JADE_DEEP, stroke=None),
        rect(38, 42, 8, 2, JADE_DEEP, stroke=None),
        rect(40, 38, 6, 2, JADE, stroke=None),
        rect(22, 46, 3, 3, GOLD, stroke=None),
    ]


def art_po_mo_fu() -> list[str]:
    """破魔符：纸符、朱砂符纹、金印与上下木杆。"""
    return [
        poly([(20, 14), (44, 14), (44, 48), (32, 54), (20, 48)], PAPER),
        rect(20, 14, 24, 4, RED, stroke=None),
        rect(28, 22, 4, 18, RED, stroke=None),
        rect(23, 26, 16, 3, RED, stroke=None),
        rect(26, 36, 12, 3, GOLD_DEEP, stroke=None),
        circle(32, 44, 3, GOLD),
        rect(16, 9, 32, 5, WOOD),
        rect(18, 8, 4, 7, GOLD, stroke=None),
        rect(42, 8, 4, 7, GOLD, stroke=None),
        poly([(24, 20), (28, 16), (30, 22), (26, 25)], GOLD_LIGHT, stroke=None),
    ]


def art_xuan_tie_jia() -> list[str]:
    """玄铁甲：胸甲、双肩甲、金色束带与中心玉扣。"""
    return [
        poly(
            [(20, 18), (28, 14), (36, 14), (44, 18), (48, 26), (46, 44),
             (38, 52), (26, 52), (18, 44), (16, 26)],
            IRON,
        ),
        poly(
            [(22, 21), (29, 17), (35, 17), (42, 21), (45, 27), (43, 42),
             (37, 48), (27, 48), (21, 42), (19, 27)],
            IRON_LIGHT, stroke=None,
        ),
        poly([(14, 20), (22, 16), (24, 28), (16, 30)], IRON_DEEP),
        poly([(50, 20), (42, 16), (40, 28), (48, 30)], IRON_DEEP),
        rect(22, 30, 20, 3, GOLD),
        rect(27, 40, 10, 3, GOLD_DEEP, stroke=None),
        circle(32, 35, 3, JADE),
        rect(31, 22, 2, 6, IRON_DEEP, stroke=None),
        rect(18, 32, 3, 3, GOLD_LIGHT, stroke=None),
        rect(43, 32, 3, 3, GOLD_LIGHT, stroke=None),
    ]


ART: dict[str, Callable[[], list[str]]] = {
    "qing_feng_jian": art_qing_feng_jian,
    "liao_shang_dan": art_liao_shang_dan,
    "ling_cao": art_ling_cao,
    "han_tie": art_han_tie,
    "yun_mu": art_yun_mu,
    "jiao_gu": art_jiao_gu,
    "jiu_ye": art_jiu_ye,
    "xuan_jing": art_xuan_jing,
    "gu_ti_dan": art_gu_ti_dan,
    "hui_ling_dan": art_hui_ling_dan,
    "ju_qi_dan": art_ju_qi_dan,
    "po_jing_dan": art_po_jing_dan,
    "yang_shen_dan": art_yang_shen_dan,
    "hu_xin_jing": art_hu_xin_jing,
    "ju_ling_pei": art_ju_ling_pei,
    "liu_yun_xue": art_liu_yun_xue,
    "po_mo_fu": art_po_mo_fu,
    "xuan_tie_jia": art_xuan_tie_jia,
}

KIND_ORDER = {"material": 0, "pill": 1, "artifact": 2}


def load_items() -> list[dict[str, str]]:
    """读取真实配置，返回按材料、丹药、法器排序的道具清单。"""
    items: list[dict[str, str]] = []
    seen: set[str] = set()

    folders = (("recipes", None), ("materials", "material"))
    for folder, forced_kind in folders:
        for path in sorted((CONFIG_DIR / folder).glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            item_id = str(data["id"])
            if item_id in seen:
                raise IconError(f"配置中存在重复 ID：{item_id}")
            seen.add(item_id)
            items.append({
                "id": item_id,
                "name": str(data["name"]),
                "kind": forced_kind or str(data["kind"]),
            })

    items.sort(key=lambda item: (KIND_ORDER.get(item["kind"], 9), item["id"]))
    return items


def render_svg(item: dict[str, str]) -> str:
    """把一件道具画成完整 SVG 文本。"""
    painter = ART.get(item["id"])
    if painter is None:
        raise IconError(f"{item['id']}（{item['name']}）缺少本地绘图定义")
    body = "\n".join(f"  {element}" for element in painter())
    title = html.escape(item["name"])
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
        'width="64" height="64" shape-rendering="crispEdges" role="img">\n'
        f"  <title>{title}</title>\n"
        f"{body}\n"
        "</svg>\n"
    )


def _write_if_changed(path: Path, content: str) -> bool:
    """内容一致时不重写，保持重复运行零差异。"""
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def generate(
    items: list[dict[str, str]], output: Path, only: set[str] | None = None,
) -> list[Path]:
    """生成 SVG 与 index.json，返回实际写入的文件路径。"""
    selected_items = items
    if only:
        unknown = only - {item["id"] for item in items}
        if unknown:
            raise IconError(f"未知道具 ID：{', '.join(sorted(unknown))}")
        selected_items = [item for item in items if item["id"] in only]

    output.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for item in selected_items:
        path = output / f"{item['id']}.svg"
        if _write_if_changed(path, render_svg(item)):
            written.append(path)

    # 单图更新后仍登记目录中其余已生成道具，避免完整总览被开发预览缩减。
    manifest = {
        "items": [
            {
                "id": item["id"],
                "name": item["name"],
                "kind": item["kind"],
                "file": f"{item['id']}.svg",
            }
            for item in items
            if (output / f"{item['id']}.svg").is_file()
        ]
    }
    manifest_path = output / "index.json"
    content = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if _write_if_changed(manifest_path, content):
        written.append(manifest_path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成本地像素风道具图标")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="输出目录")
    parser.add_argument("--only", default="", help="仅生成逗号分隔的指定 ID（开发预览用）")
    args = parser.parse_args(argv)

    only = {value.strip() for value in args.only.split(",") if value.strip()}
    try:
        items = load_items()
        written = generate(items, args.output, only or None)
    except (IconError, KeyError, json.JSONDecodeError) as error:
        print(f"生成失败：{error}", file=sys.stderr)
        return 1

    print(f"道具配置 {len(items)} 项，输出目录 {args.output}")
    print(f"本次写入 {len(written)} 个文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
