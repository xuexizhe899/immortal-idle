#!/usr/bin/env python3
"""拦截绕过确定性随机源的写法。

规则：
  * Python 禁止 `import random` / `from random import ...`
  * 前端禁止 `Math.random(`

只扫 backend/app 与 frontend/src，命中即失败。CI 里跑，防止有人图省事直接调系统随机。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (ROOT / "backend" / "app", ROOT / "frontend" / "src")
SUFFIXES = {".py", ".ts", ".vue", ".js"}
SKIP_PARTS = {"node_modules", "dist", "generated", ".venv", "__pycache__"}

PY_PATTERN = re.compile(r"^\s*(?:import\s+random\b|from\s+random\s+import\b)", re.MULTILINE)
JS_PATTERN = re.compile(r"\bMath\.random\s*\(")


def main() -> int:
    """扫描目标目录并打印违规位置。"""
    hits: list[str] = []

    for target in TARGETS:
        for path in target.rglob("*"):
            if not path.is_file() or path.suffix not in SUFFIXES:
                continue
            if SKIP_PARTS & set(path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            pattern = PY_PATTERN if path.suffix == ".py" else JS_PATTERN
            for match in pattern.finditer(text):
                line = text[: match.start()].count("\n") + 1
                hits.append(f"{path.relative_to(ROOT).as_posix()}:{line}")

    if hits:
        print("[rng] 发现绕过确定性随机源的调用：")
        for hit in hits:
            print(f"  - {hit}")
        return 1

    print("[rng] ok: 未发现 import random / Math.random")
    return 0


if __name__ == "__main__":
    sys.exit(main())
