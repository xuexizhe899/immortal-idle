#!/usr/bin/env python3
"""生成美术前置的四件物品样稿；不接入正式物品配置。

作者：XX
运行：backend/.venv/Scripts/python.exe tools/generate_art_foundation_items.py
只写 frontend/public/assets/art-foundation/items/ 下的八张 SVG。
图标与展示图使用独立构图，透明底、固定坐标、无外部资产和随机数。
"""

from html import escape
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / "frontend/public/assets/art-foundation/items"
INK = "#243B38"
DEEP = "#172D2C"
JADE = "#537D70"
JADE_LIGHT = "#94B8A0"
JADE_DARK = "#36584F"
IVORY = "#EDE8D2"
WHITE = "#FAF5E2"
CERAMIC = "#C5D0BD"
CERAMIC_SHADOW = "#8FA99B"
IRON = "#8CABA9"
IRON_LIGHT = "#D3DED3"
IRON_DARK = "#526F70"
BRONZE = "#A77B4D"
BRONZE_LIGHT = "#D7B979"
BRONZE_DARK = "#715B40"
RED = "#A35844"
RED_DARK = "#713E35"
RED_LIGHT = "#D29268"


def polygon(points: str, fill: str, stroke: str | None = None, width: int = 2) -> str:
    edge = f' stroke="{stroke}" stroke-width="{width}" stroke-linejoin="miter"' if stroke else ""
    return f'<polygon points="{points}" fill="{fill}"{edge}/>'


def rect(x: int, y: int, w: int, h: int, fill: str) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"/>'


def line(points: str, color: str, width: int = 2) -> str:
    return f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="miter"/>'


def healing_pill(detail: bool) -> list[str]:
    """白瓷葫芦、草药塞与朱绳让疗伤用途在缩小时仍可辨认。"""
    if not detail:
        return [
            polygon("27,8 38,8 38,15 41,18 43,23 42,29 38,33 43,38 46,45 46,52 42,58 23,58 18,53 18,44 21,38 27,33 23,28 23,20 27,16", IVORY, INK),
            polygon("36,18 40,22 40,27 35,32 36,38 41,42 42,51 39,55 34,55 37,49 36,42 32,37 31,32 35,27", CERAMIC_SHADOW),
            polygon("27,21 30,18 33,18 31,23 31,28 27,27", WHITE),
            polygon("23,42 28,38 30,40 26,46 26,51 23,51", WHITE),
            rect(25,30,15,5,RED_DARK), rect(25,30,13,3,RED),
            polygon("34,33 38,33 41,42 39,45 36,38", RED),
            polygon("29,32 34,32 35,38 31,41 27,38", BRONZE_LIGHT, BRONZE_DARK, 1),
            rect(28,9,10,5,BRONZE_DARK), rect(28,8,9,3,BRONZE),
            polygon("32,8 28,4 29,2 33,4 34,8", JADE_DARK),
            polygon("34,8 35,3 41,2 39,6", JADE),
            rect(27,53,11,2,CERAMIC),
        ]
    return [
        polygon("82,34 110,34 110,46 119,54 126,66 128,79 124,89 113,99 122,107 133,118 140,134 141,151 136,165 126,175 112,179 76,179 62,174 52,164 47,151 48,136 54,121 65,109 78,100 67,90 62,80 63,67 69,54 82,45", INK),
        polygon("83,38 107,38 107,48 116,57 122,68 123,79 119,87 108,97 106,102 118,111 129,122 135,136 136,150 131,162 122,170 109,174 77,174 65,170 57,161 52,149 53,137 59,124 68,114 82,104 83,98 72,88 67,79 68,68 74,57 83,48", IVORY),
        polygon("108,48 118,58 123,70 123,79 116,91 105,99 107,106 121,117 130,131 133,145 131,156 123,166 111,171 102,171 111,162 115,149 114,136 108,124 96,113 94,102 100,91 107,83 110,72 107,62", CERAMIC),
        polygon("122,123 132,137 133,148 128,161 118,169 106,171 116,158 120,145 117,131", CERAMIC_SHADOW),
        polygon("78,56 85,51 91,51 87,62 83,74 84,83 78,86 73,79 73,70", WHITE),
        polygon("63,129 73,118 82,115 84,120 76,131 71,146 71,157 64,157 59,146", WHITE),
        polygon("73,166 85,170 101,170 101,173 78,173 68,169", CERAMIC),
        rect(77,96,34,6,RED_DARK), rect(75,94,37,5,RED),
        rect(78,95,22,2,RED_LIGHT),
        polygon("103,98 111,101 117,114 114,122 110,117 109,109", RED_DARK),
        polygon("100,99 106,102 108,114 104,129 100,125 104,113", RED),
        polygon("93,99 105,99 108,108 104,118 95,123 86,115 87,105", BRONZE_DARK),
        polygon("94,101 102,101 105,108 101,115 95,118 90,113 91,106", BRONZE_LIGHT),
        rect(95,106,5,2,BRONZE), rect(94,110,7,2,BRONZE),
        polygon("80,36 81,25 86,21 105,21 112,25 111,36", BRONZE_DARK, INK),
        rect(84,26,23,6,BRONZE), rect(86,23,18,3,BRONZE_LIGHT),
        rect(87,33,17,3,RED_DARK),
        polygon("92,23 83,18 78,11 80,6 87,9 92,16 97,21", JADE_DARK),
        polygon("96,22 98,11 106,5 115,5 112,13 104,19", JADE),
        polygon("99,20 104,12 110,9 105,16", JADE_LIGHT),
        line("81,10 86,14 91,20", JADE, 2),
        polygon("77,141 80,134 85,132 89,136 87,141 82,145", CERAMIC),
        line("80,138 83,137 86,138", CERAMIC_SHADOW, 2),
        rect(111,71,3,8,WHITE), rect(58,140,2,7,IVORY),
    ]


def breakthrough_pill(detail: bool) -> list[str]:
    """朱砂丹置于青铜丹盒；开口与丹纹区别于瓶装疗伤药。"""
    if not detail:
        return [
            polygon("11,37 18,31 45,31 53,37 53,51 45,58 19,58 11,51", BRONZE_DARK, INK),
            polygon("13,38 20,34 44,34 51,38 44,44 20,44", BRONZE, INK, 1),
            polygon("15,39 22,36 42,36 49,39 43,42 21,42", JADE_DARK),
            polygon("20,12 27,7 37,7 44,12 47,21 44,30 38,35 27,35 20,30 17,21", RED_DARK, INK),
            polygon("22,12 28,9 36,9 41,13 44,21 41,28 36,32 27,32 22,28 20,21", RED),
            polygon("23,14 28,11 33,11 29,16 25,19 22,18", RED_LIGHT),
            line("27,27 27,22 33,17 38,18 38,23 32,27 32,31", BRONZE_LIGHT, 2),
            polygon("13,43 21,47 43,47 51,43 51,50 44,55 20,55 13,50", JADE_DARK),
            line("17,47 22,50 42,50 47,47", BRONZE, 2),
            rect(29,47,6,7,BRONZE_LIGHT), rect(31,48,2,3,BRONZE_DARK),
        ]
    return [
        polygon("31,113 52,96 139,96 162,113 162,151 142,171 53,171 31,151", INK),
        polygon("35,115 55,101 137,101 158,115 139,132 55,132", BRONZE),
        polygon("43,115 58,106 133,106 150,115 135,126 58,126", BRONZE_LIGHT),
        polygon("49,115 62,110 130,110 143,115 131,121 62,121", JADE_DARK),
        polygon("35,123 54,137 139,137 158,123 158,149 140,166 55,166 35,149", BRONZE_DARK),
        polygon("40,131 57,143 135,143 153,131 153,148 137,161 57,161 40,148", JADE_DARK),
        polygon("44,137 58,147 133,147 146,139 146,147 133,156 58,156 44,146", JADE),
        rect(61,151,68,3,BRONZE),
        polygon("60,35 76,24 104,21 125,32 137,48 140,72 132,94 115,111 87,118 64,110 48,92 44,69 48,49", INK),
        polygon("62,39 77,28 103,25 122,35 133,51 135,72 128,92 112,107 88,113 67,105 53,89 49,69 53,51", RED_DARK),
        polygon("62,40 78,29 101,27 121,37 130,53 130,70 123,86 109,96 88,99 68,94 55,81 52,64 55,51", RED),
        polygon("63,43 79,33 98,31 105,35 89,39 76,44 65,55 58,67 56,59", RED_LIGHT),
        polygon("61,48 67,44 72,45 67,52 62,55 59,54", IVORY),
        polygon("118,45 128,56 129,71 120,87 108,94 110,87 119,75 121,60", "#8B493C"),
        line("71,92 72,80 88,69 88,54 99,45 112,49 113,60 104,66 94,66 83,78 83,91 94,101", BRONZE_DARK, 5),
        line("70,89 70,78 85,67 85,53 97,43 109,47 110,58 102,63 93,63 80,76 80,89 91,99", BRONZE_LIGHT, 3),
        line("93,64 102,73 102,83 95,89 88,86", BRONZE_LIGHT, 2),
        rect(89,143,17,24,INK), rect(92,143,11,21,BRONZE),
        rect(93,144,9,4,BRONZE_LIGHT), rect(96,151,3,6,BRONZE_DARK),
        line("49,144 56,149 56,156", BRONZE_LIGHT, 2),
        line("143,141 136,147 136,154", BRONZE, 2),
        rect(62,139,13,2,BRONZE_LIGHT), rect(118,139,11,2,BRONZE),
    ]


def ordinary_sword(detail: bool) -> list[str]:
    """青锋剑保留可信的直刃、中央脊线、护手与缠柄结构。"""
    if not detail:
        return [
            polygon("19,43 47,9 57,5 55,16 28,49", INK),
            polygon("23,41 48,12 54,8 52,16 27,45", IRON),
            polygon("24,40 48,12 54,8 48,18 25,44", IRON_LIGHT),
            polygon("26,44 49,17 52,13 51,18 29,46", IRON_DARK),
            polygon("14,37 17,35 33,49 30,52 25,49 18,43", BRONZE_DARK, INK, 1),
            polygon("15,37 18,37 31,49 29,49", BRONZE_LIGHT),
            polygon("10,52 20,42 25,47 15,58", RED_DARK, INK, 1),
            line("15,48 20,51", BRONZE, 2), line("12,52 17,55", BRONZE, 2),
            polygon("7,53 10,51 17,57 14,61 10,61 6,57", BRONZE, INK, 1),
            polygon("10,54 14,58 12,59 9,57", BRONZE_LIGHT),
            line("29,51 31,57 27,60", JADE_DARK, 2),
        ]
    return [
        polygon("55,131 141,30 172,14 163,48 83,146", INK),
        polygon("61,129 143,34 166,21 159,46 81,139", IRON),
        polygon("62,128 143,34 166,21 144,48 72,135", IRON_LIGHT),
        polygon("72,135 144,48 165,23 156,46 80,137", IRON_DARK),
        polygon("66,127 139,43 141,44 72,127", WHITE),
        polygon("141,35 157,27 147,40 144,40", WHITE),
        polygon("80,129 151,46 153,45 84,129", "#759590"),
        polygon("107,82 110,80 112,80 109,84", IRON_LIGHT),
        polygon("88,106 91,103 94,103 91,107", IRON_DARK),
        polygon("44,112 50,108 58,114 87,141 91,149 86,155 78,152 57,131 46,123", INK),
        polygon("47,114 51,112 59,118 84,142 87,149 84,151 79,148 55,125 48,121", BRONZE),
        polygon("48,114 51,112 60,119 81,140 80,143 55,122 49,119", BRONZE_LIGHT),
        polygon("58,125 65,119 77,130 70,137", BRONZE_DARK),
        polygon("61,125 65,122 73,130 70,133", JADE_DARK),
        polygon("28,158 55,129 69,142 42,172", INK),
        polygon("33,158 56,134 64,142 41,166", RED_DARK),
        polygon("33,157 55,134 58,137 36,160", RED),
        line("49,141 58,149", BRONZE, 3),
        line("44,147 53,155", BRONZE, 3),
        line("38,153 47,161", BRONZE, 3),
        polygon("22,160 28,156 46,171 44,178 38,182 29,179 21,170", INK),
        polygon("25,162 29,160 42,172 40,176 36,178 30,175 25,169", BRONZE),
        polygon("25,162 29,160 40,170 36,171 27,166", BRONZE_LIGHT),
        polygon("30,168 34,167 38,172 35,175", JADE_DARK),
        line("84,153 91,159 90,171 84,179", JADE_DARK, 4),
        line("85,154 89,160 88,170", JADE, 2),
        polygon("83,174 89,175 90,184 84,182 80,184", JADE_DARK),
    ]


def guanyu_glaive(detail: bool) -> list[str]:
    """偃月刀以大刃、龙脊、铜箍与深青长柄表达专属身份。"""
    if not detail:
        return [
            polygon("10,57 35,26 40,30 15,62", INK),
            polygon("12,57 36,28 38,30 14,59", JADE_DARK),
            line("14,56 32,34", JADE_LIGHT, 1),
            polygon("33,29 35,19 43,10 53,6 61,6 55,12 54,18 58,24 61,27 57,33 49,36 40,35", INK),
            polygon("36,27 38,20 45,12 54,9 58,9 52,14 52,21 57,27 54,30 47,33 41,32", IRON),
            polygon("39,25 40,20 47,13 55,10 51,15 50,23 55,28 50,30 46,29", IRON_LIGHT),
            polygon("35,28 39,24 42,26 44,31 41,35 36,34 33,31", BRONZE_DARK, INK, 1),
            polygon("36,28 39,26 41,28 39,30 41,32 38,33 35,31", BRONZE_LIGHT),
            rect(39,27,2,2,DEEP),
            line("39,25 43,19 46,18 45,23 48,26", BRONZE, 2),
            polygon("26,38 30,34 34,37 31,41", BRONZE, INK, 1),
            polygon("9,57 12,55 17,59 14,63 11,63 8,60", BRONZE, INK, 1),
            polygon("30,37 34,37 34,45 30,48 29,44", RED),
        ]
    return [
        polygon("25,169 111,64 122,73 35,180", INK),
        polygon("29,169 112,68 117,73 34,174", JADE_DARK),
        polygon("30,168 110,71 112,73 33,170", JADE_LIGHT),
        polygon("33,171 114,73 117,74 36,174", DEEP),
        polygon("103,79 107,56 121,37 140,24 159,17 180,17 172,29 164,37 162,48 168,62 181,75 174,85 159,94 139,99 121,97 111,90", INK),
        polygon("108,78 112,58 124,40 142,28 160,22 173,22 166,31 159,37 157,49 163,65 174,75 170,81 157,89 139,94 123,92 115,87", IRON_DARK),
        polygon("112,73 116,57 127,42 144,31 160,26 166,26 156,37 153,49 157,63 168,75 163,81 151,86 138,88 126,85", IRON),
        polygon("116,65 121,52 131,41 146,32 160,28 151,37 147,48 149,63 159,76 150,81 137,81 127,76", IRON_LIGHT),
        polygon("123,51 133,41 148,32 159,29 149,37 136,42 128,50", WHITE),
        polygon("165,66 175,75 169,82 157,88 140,93 127,90 127,87 141,89 156,84 167,78", IRON_LIGHT),
        polygon("145,58 148,59 151,66 149,69 145,65", "#AAC3B8"),
        polygon("112,72 118,61 127,57 133,49 141,47 147,52 147,58 140,63 140,69 147,74 144,81 136,84 130,78 123,79 118,87 109,87 105,81", BRONZE_DARK, INK),
        polygon("111,74 120,65 128,63 135,54 141,52 144,54 143,57 136,60 134,65 137,71 142,75 140,79 136,80 131,74 122,75 115,83 110,83 109,80", BRONZE),
        polygon("113,74 120,67 129,65 136,56 140,54 142,55 135,61 131,68 122,69 115,77 111,80", BRONZE_LIGHT),
        polygon("132,65 138,62 142,64 142,68 138,72 133,70", JADE_DARK),
        rect(136,64,3,3,BRONZE_LIGHT),
        polygon("113,80 118,77 123,79 120,84 115,86", BRONZE_LIGHT),
        line("118,72 121,70 125,71", INK, 2),
        line("126,65 130,64 133,65", BRONZE_DARK, 2),
        polygon("89,100 96,92 106,100 99,109", INK),
        polygon("92,100 97,95 103,100 98,105", BRONZE),
        line("94,99 98,97 101,100", BRONZE_LIGHT, 2),
        polygon("72,120 78,113 87,120 81,128", INK),
        polygon("75,120 79,116 84,120 80,125", BRONZE_DARK),
        polygon("91,103 97,106 99,119 93,133 88,130 93,116", RED_DARK),
        polygon("93,105 96,107 96,117 90,128 90,121 94,114", RED),
        polygon("23,169 28,165 39,174 38,182 31,187 24,181 21,175", INK),
        polygon("26,170 29,169 36,175 35,180 31,183 26,179 25,175", BRONZE),
        polygon("26,170 29,169 35,174 32,176 27,174", BRONZE_LIGHT),
        rect(29,177,3,3,BRONZE_DARK),
        line("54,143 60,148", BRONZE_DARK, 2),
        line("58,138 64,143", BRONZE_DARK, 2),
    ]


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    subjects = (
        ("liao_shang_dan", "疗伤丹", healing_pill),
        ("po_jing_dan", "破境丹", breakthrough_pill),
        ("qing_feng_jian", "青锋剑", ordinary_sword),
        ("guanyu_signature", "关羽专属偃月刀视觉概念", guanyu_glaive),
    )
    for item_id, name, draw in subjects:
        for variant, size in (("icon", 64), ("display", 192)):
            body = "\n  ".join(draw(variant == "display"))
            svg = (
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
                f'width="{size}" height="{size}" shape-rendering="crispEdges" role="img">\n'
                f'  <title>{escape(name)}</title>\n'
                f'  <desc>XX · 本地程序绘制 · 细像素修仙物品美术样稿 · {variant}</desc>\n'
                f'  {body}\n</svg>\n'
            )
            filename = f"{item_id}_display.svg" if variant == "display" else f"{item_id}.svg"
            destination = OUTPUT / filename
            destination.write_text(svg, encoding="utf-8", newline="\n")
            print(destination.relative_to(OUTPUT.parents[4]).as_posix())


if __name__ == "__main__":
    main()
