"""Asset pipeline checks run without contacting or billing the image service."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import httpx
except ImportError:
    raise unittest.SkipTest("asset pipeline checks require httpx")

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location("gen_assets", TOOLS / "gen_assets.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


class AssetPipelineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.raw = self.root / "assets" / "raw"
        self.style = self.root / "style.json"
        self.style.write_text(json.dumps({"version": "test", "style_prompt": "pixel art", "size": "1024x1536", "fallback_size": "1024x1024"}), encoding="utf-8")
        self.preset = self.root / "preset.json"
        self.preset.write_text(json.dumps({"items": [{"key": "one", "file": "one.png", "subject": "scholar"}]}), encoding="utf-8")
        self.manifest = self.root / "manifest.json"
        self.patches = [
            patch.object(gen, "ROOT", self.root),
            patch.object(gen, "RAW_DIR", self.raw),
            patch.object(gen, "STYLE_PATH", self.style),
            patch.object(gen, "MANIFEST_PATH", self.manifest),
            patch.object(gen, "read_env", return_value={"CENTOS_API_KEY": "test-secret", "CENTOS_BASE_URL": "https://example.invalid", "CENTOS_MODEL": "specified-model"}),
            patch.object(sys, "argv", ["gen_assets", "--preset", "preset.json"]),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def test_uncertain_request_is_counted_and_not_resubmitted(self):
        with patch.object(gen, "request_image", side_effect=httpx.ConnectTimeout("not logged")) as request:
            self.assertEqual(gen.main(), 1)
            self.assertEqual(gen.main(), 1)
            self.assertEqual(request.call_count, 1)
        self.assertEqual(json.loads(self.manifest.read_text())["calls"], 1)

    def test_failed_download_resumes_without_generating_again(self):
        payload = {"kind": "url", "value": "https://example.invalid/image?signature=private", "usage": None}
        with patch.object(gen, "request_image", return_value=payload) as request:
            with patch.object(gen, "save_payload", side_effect=httpx.ReadTimeout("not logged")):
                self.assertEqual(gen.main(), 1)
            with patch.object(gen, "save_payload", return_value=50):
                self.assertEqual(gen.main(), 0)
            self.assertEqual(request.call_count, 1)
        self.assertNotIn("signature", self.manifest.read_text())
        self.assertFalse((self.raw / "one.png.pending.json").exists())

    def test_missing_ignored_raw_restores_master_without_an_api_call(self):
        master = self.root / "assets" / "masters" / "one.png"
        master.parent.mkdir(parents=True)
        master.write_bytes(b"preserved original")
        prompt = gen.build_prompt(json.loads(self.style.read_text()), {"subject": "scholar"})
        image_hash = gen.digest("test", "specified-model", "1024x1536", prompt)
        self.manifest.write_text(json.dumps({"calls": 1, "items": [{"key": "one", "hash": image_hash, "file": "assets/raw/one.png", "master": "assets/masters/one.png"}]}))
        with patch.object(gen, "request_image") as request:
            with patch.object(sys, "argv", ["gen_assets", "--preset", "preset.json", "--dry-run"]):
                self.assertEqual(gen.main(), 0)
                self.assertFalse((self.raw / "one.png").exists())
            self.assertEqual(gen.main(), 0)
            request.assert_not_called()
        self.assertEqual((self.raw / "one.png").read_bytes(), b"preserved original")

    def test_provider_error_does_not_expose_credentials(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(401, text="test-secret https://example.invalid/?private=secret"))
        with httpx.Client(transport=transport) as client:
            with self.assertRaises(gen.GenerationError) as caught:
                gen.request_image(client, "https://example.invalid", "test-secret", "specified-model", "portrait", "1024x1536")
        self.assertFalse(caught.exception.unsupported_size)
        self.assertEqual(str(caught.exception), "HTTP 401: image request rejected")

    def test_only_explicit_size_error_allows_fallback(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(400, text="unsupported size"))
        with httpx.Client(transport=transport) as client:
            with self.assertRaises(gen.GenerationError) as caught:
                gen.request_image(client, "https://example.invalid", "test-secret", "specified-model", "portrait", "1024x1536")
        self.assertTrue(caught.exception.unsupported_size)

    def test_alpha_trim_preserves_transparency(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("alpha checks require Pillow")
        from normalize_assets import trim

        image = Image.new("RGBA", (20, 20), (255, 0, 255, 0))
        image.paste((20, 70, 40, 255), (7, 5, 13, 15))
        trimmed = trim(image)
        self.assertEqual(trimmed.mode, "RGBA")
        self.assertEqual(trimmed.size, (6, 10))

    def test_key_removes_dark_magenta_spill_but_keeps_jade_and_crimson(self):
        try:
            from chroma_key import is_magenta
        except ImportError:
            self.skipTest("key checks require Pillow")
        self.assertTrue(is_magenta(120, 20, 140))
        self.assertTrue(is_magenta(242, 15, 242))
        self.assertFalse(is_magenta(40, 100, 80))
        self.assertFalse(is_magenta(150, 40, 55))
        self.assertFalse(is_magenta(120, 45, 85))

    def test_key_preserves_interior_dark_purple_fabric(self):
        try:
            from PIL import Image
            from chroma_key import key_out
        except ImportError:
            self.skipTest("key checks require Pillow")
        image = Image.new("RGB", (11, 11), (242, 15, 242))
        image.paste((35, 100, 65), (2, 2, 9, 9))
        image.putpixel((5, 5), (100, 20, 130))
        result = key_out(image)
        center = result.getpixel((result.width // 2, result.height // 2))
        self.assertEqual(center, (100, 20, 130, 255))


if __name__ == "__main__":
    unittest.main()
