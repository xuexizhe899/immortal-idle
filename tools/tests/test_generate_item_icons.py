"""本地道具图标生成器的实际风险检查。

覆盖配置遗漏、重复 ID、SVG 结构、外部引用、可重复生成以及不清理公共目录。
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import generate_item_icons as gen  # noqa: E402

EXPECTED_IDS = {
    "han_tie", "jiao_gu", "jiu_ye", "ling_cao", "xuan_jing", "yun_mu",
    "gu_ti_dan", "hui_ling_dan", "ju_qi_dan", "liao_shang_dan",
    "po_jing_dan", "yang_shen_dan",
    "hu_xin_jing", "ju_ling_pei", "liu_yun_xue", "po_mo_fu",
    "qing_feng_jian", "xuan_tie_jia",
}


class ItemIconGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.output = Path(self.directory.name) / "items"

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_every_configured_item_has_art_and_manifest_entry(self) -> None:
        items = gen.load_items()
        self.assertEqual({item["id"] for item in items}, EXPECTED_IDS)
        self.assertEqual(len(items), 18)
        self.assertEqual(set(gen.ART), EXPECTED_IDS)

        gen.generate(items, self.output)
        manifest = json.loads((self.output / "index.json").read_text(encoding="utf-8"))
        self.assertEqual({entry["id"] for entry in manifest["items"]}, EXPECTED_IDS)
        for entry in manifest["items"]:
            self.assertTrue((self.output / entry["file"]).is_file(), entry["file"])

    def test_generation_is_byte_stable_and_second_run_writes_nothing(self) -> None:
        items = gen.load_items()
        gen.generate(items, self.output)
        first = {
            path.name: path.read_bytes()
            for path in sorted(self.output.iterdir())
        }

        written = gen.generate(items, self.output)
        second = {
            path.name: path.read_bytes()
            for path in sorted(self.output.iterdir())
        }

        self.assertEqual(written, [])
        self.assertEqual(first, second)

    def test_svg_has_fixed_canvas_and_no_external_or_active_content(self) -> None:
        items = gen.load_items()
        gen.generate(items, self.output)
        forbidden_tags = {"script", "foreignObject", "image", "use", "text"}
        drawing_tags = {"rect", "polygon", "circle", "path", "ellipse"}

        for item in items:
            path = self.output / f"{item['id']}.svg"
            text = path.read_text(encoding="utf-8")
            root = ET.fromstring(text)
            self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
            self.assertEqual(root.get("viewBox"), "0 0 64 64")
            self.assertEqual(root.get("shape-rendering"), "crispEdges")
            self.assertTrue(path.name.endswith(".svg"))

            for element in root.iter():
                local = element.tag.rsplit("}", 1)[-1]
                self.assertNotIn(local, forbidden_tags, f"{item['id']} 含 {local}")
                for name, value in element.attrib.items():
                    self.assertNotEqual(name, "href", f"{item['id']} 含 href")
                    self.assertNotIn("url(", value, f"{item['id']} 含外部引用")
                    self.assertNotIn("data:", value, f"{item['id']} 含内嵌数据")

            self.assertGreater(
                sum(1 for element in root.iter() if element.tag.rsplit("}", 1)[-1] in drawing_tags),
                3,
                f"{item['id']} 图形元素过少",
            )
            self.assertNotIn("<text", text)
            self.assertNotIn("<script", text)
            self.assertNotIn("<image", text)

    def test_unrelated_files_in_output_directory_are_preserved(self) -> None:
        self.output.mkdir(parents=True)
        keep = self.output / "keep.txt"
        keep.write_text("do not delete", encoding="utf-8")
        stale = self.output / "old_icon.svg"
        stale.write_text("<svg/>", encoding="utf-8")

        gen.generate(gen.load_items(), self.output)

        self.assertTrue(keep.is_file())
        self.assertTrue(stale.is_file())

    def test_missing_art_and_unknown_id_are_reported(self) -> None:
        with self.assertRaises(gen.IconError):
            gen.render_svg({"id": "not_in_art", "name": "无图", "kind": "pill"})
        with self.assertRaises(gen.IconError):
            gen.generate(gen.load_items(), self.output, {"not_in_art"})

    def test_duplicate_config_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            for folder in ("recipes", "materials"):
                (config / folder).mkdir()
            (config / "recipes" / "one.json").write_text(
                json.dumps({"id": "same", "name": "甲", "kind": "pill"}),
                encoding="utf-8",
            )
            (config / "materials" / "two.json").write_text(
                json.dumps({"id": "same", "name": "乙"}),
                encoding="utf-8",
            )
            original = gen.CONFIG_DIR
            gen.CONFIG_DIR = config
            try:
                with self.assertRaises(gen.IconError):
                    gen.load_items()
            finally:
                gen.CONFIG_DIR = original


if __name__ == "__main__":
    unittest.main()
