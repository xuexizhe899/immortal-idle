#!/usr/bin/env python3
"""Config validation entrypoint.

T00 scope: JSON syntax only, so CI wiring can be verified.
T01 adds dangling-reference checks:
  - disciple.skill -> skill table
  - disciple.bonds -> config/bonds
  - disciple.lean in {attack, defense, support, craft}
  - disciple.asset_id -> frontend/public/assets
  - mode configs -> enemies / rewards / affix weights
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"


def iter_json_files() -> list[Path]:
    return sorted(p for p in CONFIG_DIR.rglob("*.json") if p.is_file())


def main() -> int:
    files = iter_json_files()
    errors: list[str] = []

    for path in files:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path.relative_to(ROOT)}: {exc}")

    if errors:
        print(f"[config] {len(errors)} error(s):")
        for item in errors:
            print(f"  - {item}")
        return 1

    print(
        f"[config] ok: {len(files)} json file(s), syntax checked "
        f"(reference checks land in T01)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
