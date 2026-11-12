"""整理美术前置的素材联系图与文件指纹，不运行游戏或访问数据库。

作者：XX
运行：backend/.venv/Scripts/python.exe tools/prepare_art_foundation_review.py
只读已制作的 SVG / PNG，输出到 artifacts/art-foundation/。
"""

import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/art-foundation"
PUBLIC = ROOT / "frontend/public"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    title_font = ImageFont.truetype(str(font_path), 25) if font_path.exists() else ImageFont.load_default()
    label_font = ImageFont.truetype(str(font_path), 17) if font_path.exists() else ImageFont.load_default()
    sheet = Image.new("RGBA", (1412, 816), "#e8e5d8")
    draw = ImageDraw.Draw(sheet)
    draw.text((28, 18), "守塔群像 · 十种敌人外观", font=title_font, fill="#273e36")
    draw.text((28, 57), "待人工审阅 / 四种现有敌人 · 六种美术储备，未接入玩法", font=label_font, fill="#65766b")
    enemies = (
        ("stone_guard", "石甲灵卫", "现有敌人"),
        ("cloud_archer", "流云弓卫", "现有敌人"),
        ("jade_warden", "玉衡守将", "现有敌人"),
        ("cinder_blade", "赤炉刀卫", "美术储备"),
        ("bamboo_swordsman", "竹隐剑客", "美术储备"),
        ("frost_crane", "霜羽鹤灵", "美术储备"),
        ("vine_spirit", "青藤木魈", "美术储备"),
        ("bronze_beast", "铜角镇兽", "美术储备"),
        ("lantern_wraith", "引魂灯使", "美术储备"),
        ("tower_master", "问道真灵", "现有敌人"),
    )
    for index, (enemy_id, label, status) in enumerate(enemies):
        left = 24 + (index % 5) * 276
        top = 96 + (index // 5) * 356
        draw.rectangle((left, top, left + 260, top + 340), fill="#f8f3e6", outline="#c6bda3")
        sprite = Image.open(PUBLIC / f"assets/art-foundation/enemies/{enemy_id}.png").convert("RGBA")
        # 鹤与四足灵兽同时受宽高约束，长喙、角和尾巴不能越过联系图格子。
        scale = min(236 / sprite.width, 244 / sprite.height)
        width = max(1, round(sprite.width * scale))
        height = max(1, round(sprite.height * scale))
        sprite = sprite.resize((width, height), Image.Resampling.NEAREST)
        sheet.alpha_composite(sprite, (left + (260 - width) // 2, top + 12 + (244 - height) // 2))
        draw.text((left + 18, top + 274), label, font=label_font, fill="#426854")
        draw.text((left + 18, top + 303), status, font=label_font, fill="#7b7967")
    sheet.convert("RGB").save(OUTPUT / "enemy-contact-sheet.png", optimize=True)

    # 联系图保留四件本地 SVG 的原始矢量，不调用浏览器或重写运行资产。
    namespace = "http://www.w3.org/2000/svg"
    ET.register_namespace("", namespace)
    contact = ET.Element(f"{{{namespace}}}svg", {"viewBox": "0 0 944 320", "width": "944", "height": "320"})
    ET.SubElement(contact, f"{{{namespace}}}rect", {"width": "944", "height": "320", "fill": "#e8e5d8"})
    heading = ET.SubElement(contact, f"{{{namespace}}}text", {"x": "24", "y": "32", "fill": "#273e36", "font-family": "Microsoft YaHei, sans-serif", "font-size": "20"})
    heading.text = "丹药与武器 · 代表试稿（待人工审阅）"
    for index, (item_id, label) in enumerate((("liao_shang_dan", "疗伤丹"), ("po_jing_dan", "破境丹"), ("qing_feng_jian", "青锋剑"), ("guanyu_signature", "关羽专武 · 外观概念"))):
        left = 24 + index * 230
        ET.SubElement(contact, f"{{{namespace}}}rect", {"x": str(left), "y": "52", "width": "206", "height": "242", "fill": "#f8f3e6", "stroke": "#c6bda3"})
        group = ET.SubElement(contact, f"{{{namespace}}}g", {"transform": f"translate({left + 19} 65) scale(.875)", "shape-rendering": "crispEdges"})
        source = ET.parse(PUBLIC / f"assets/art-foundation/items/{item_id}_display.svg").getroot()
        for child in source:
            if child.tag.rsplit("}", 1)[-1] not in {"title", "desc"}:
                group.append(child)
        text = ET.SubElement(contact, f"{{{namespace}}}text", {"x": str(left + 14), "y": "267", "fill": "#426854", "font-family": "Microsoft YaHei, sans-serif", "font-size": "14"})
        text.text = label
    ET.ElementTree(contact).write(OUTPUT / "item-contact-sheet.svg", encoding="utf-8", xml_declaration=True)

    records = []
    paths = sorted((PUBLIC / "assets/art-foundation").rglob("*"))
    paths += sorted((ROOT / "assets/masters/art-foundation-enemies").glob("*.png"))
    for path in paths:
        if not path.is_file():
            continue
        record = {"file": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        if path.suffix == ".png":
            with Image.open(path) as picture:
                record.update(width=picture.width, height=picture.height, mode=picture.mode)
        records.append(record)
    manifest = json.loads((ROOT / "assets/manifest.json").read_text(encoding="utf-8"))
    calls = sum(attempt.get("key", "").startswith("art_foundation_") for attempt in manifest.get("attempts", []))
    (OUTPUT / "assets.json").write_text(json.dumps({"status": "awaiting_manual_review", "model": "gpt-image-2.6-sunburst", "authorized_call_limit": 40, "generation_calls": calls, "assets": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared contact sheets and {len(records)} asset records in artifacts/art-foundation/")


if __name__ == "__main__":
    main()
