"""静态配置加载：进程内只读一次，运行期不再重读磁盘。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _load_dir(folder: Path) -> dict[str, dict]:
    """读取目录下所有 JSON，按 id 建索引。"""
    return {
        data["id"]: data
        for path in sorted(folder.glob("*.json"))
        for data in [json.loads(path.read_text(encoding="utf-8"))]
    }


@lru_cache(maxsize=1)
def load_disciples() -> dict[str, dict]:
    """弟子模板配置，按 id 索引；首次调用后常驻内存。"""
    return _load_dir(CONFIG_DIR / "disciples")


@lru_cache(maxsize=1)
def load_affixes() -> list[dict]:
    """词条配置列表；目录为空时返回空列表，出征就跳过三选一。"""
    return list(_load_dir(CONFIG_DIR / "affixes").values())


@lru_cache(maxsize=1)
def load_modes() -> dict[str, dict]:
    """出征模式配置，按 id 索引。"""
    return _load_dir(CONFIG_DIR / "modes")


@lru_cache(maxsize=1)
def load_bonds() -> dict[str, dict]:
    """羁绊配置，按 id 索引。"""
    return _load_dir(CONFIG_DIR / "bonds")


@lru_cache(maxsize=1)
def load_recipes() -> dict[str, dict]:
    """丹方与器方配置，按 id 索引。"""
    return _load_dir(CONFIG_DIR / "recipes")


@lru_cache(maxsize=1)
def load_materials() -> dict[str, dict]:
    """材料配置，按 id 索引。"""
    return _load_dir(CONFIG_DIR / "materials")


@lru_cache(maxsize=1)
def load_skills() -> dict[str, dict]:
    """技能仅用于图鉴，当前总战力引擎不执行技能。"""
    return _load_dir(CONFIG_DIR / "skills")


@lru_cache(maxsize=1)
def load_city() -> dict:
    """主城布局：背景图与建筑热区坐标。"""
    return json.loads((CONFIG_DIR / "ui" / "city.json").read_text(encoding="utf-8"))
