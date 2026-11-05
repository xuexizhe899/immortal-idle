"""tools/validate_config.py 的单元测试。

运行：backend/.venv/Scripts/python.exe -m pytest tools/tests -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import validate_config as vc  # noqa: E402


def write_json(path: Path, data: dict) -> None:
    """把 dict 写成 UTF-8 JSON 文件，自动创建父目录。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def patch(path: Path, **changes: object) -> None:
    """读取 JSON，覆盖指定字段后写回。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(changes)
    write_json(path, data)


@pytest.fixture()
def tree(tmp_path: Path) -> tuple[Path, Path]:
    """构造一棵最小的合法配置树（两个技能、一个弟子、一张资产）。"""
    config = tmp_path / "config"
    assets = tmp_path / "assets"
    assets.mkdir(parents=True)

    write_json(
        config / "skills" / "s1.json",
        {
            "id": "s1",
            "name": "S1",
            "type": "active",
            "effects": [
                {"stat": "atk", "mode": "add_pct", "value": 0.1, "scope": "battle"}
            ],
        },
    )
    write_json(
        config / "skills" / "p1.json",
        {
            "id": "p1",
            "name": "P1",
            "type": "passive",
            "effects": [
                {
                    "stat": "material_rate",
                    "mode": "add_pct",
                    "value": 0.1,
                    "scope": "duty",
                }
            ],
        },
    )
    write_json(
        config / "disciples" / "d1.json",
        {
            "id": "d1",
            "name": "D1",
            "origin": "myth",
            "rarity": 1,
            "lean": "attack",
            "asset_id": "d1",
            "base_stats": {"hp": 10, "atk": 3, "def": 2, "spd": 4},
            "skill": "s1",
            "passive": "p1",
            "bonds": [],
        },
    )
    (assets / "d1.png").write_bytes(b"\x89PNG\r\n")
    return config, assets


def test_valid_tree_has_no_errors(tree: tuple[Path, Path]) -> None:
    """合法配置不应产生任何错误。"""
    config, assets = tree
    assert vc.validate(config, assets) == []


def test_missing_skill_is_reported(tree: tuple[Path, Path]) -> None:
    """弟子引用不存在的技能时应报错。"""
    config, assets = tree
    patch(config / "disciples" / "d1.json", skill="nope")
    errors = vc.validate(config, assets)
    assert any("skill 'nope' 不存在于 config/skills" in e for e in errors)


def test_skill_type_mismatch_is_reported(tree: tuple[Path, Path]) -> None:
    """主动技能位不能引用被动技能。"""
    config, assets = tree
    patch(config / "disciples" / "d1.json", skill="p1")
    errors = vc.validate(config, assets)
    assert any("的 type 必须是 active" in e for e in errors)


def test_missing_bond_is_reported(tree: tuple[Path, Path]) -> None:
    """弟子引用不存在的羁绊时应报错。"""
    config, assets = tree
    patch(config / "disciples" / "d1.json", bonds=["ghost_bond"])
    errors = vc.validate(config, assets)
    assert any("不存在于 config/bonds" in e for e in errors)


def test_missing_asset_is_reported(tree: tuple[Path, Path]) -> None:
    """asset_id 找不到对应 PNG 时应报错。"""
    config, assets = tree
    (assets / "d1.png").unlink()
    errors = vc.validate(config, assets)
    assert any("缺少 frontend/public/assets/d1.png" in e for e in errors)


def test_invalid_lean_is_reported(tree: tuple[Path, Path]) -> None:
    """倾向值不在四类枚举内时应报错。"""
    config, assets = tree
    patch(config / "disciples" / "d1.json", lean="tank")
    errors = vc.validate(config, assets)
    assert any("lean 'tank'" in e for e in errors)


def test_id_must_match_filename(tree: tuple[Path, Path]) -> None:
    """id 与文件名不一致时应报错。"""
    config, assets = tree
    write_json(
        config / "skills" / "p2.json",
        {"id": "p9", "name": "P2", "type": "passive", "effects": []},
    )
    errors = vc.validate(config, assets)
    assert any("必须与文件名 'p2' 一致" in e for e in errors)


def test_invalid_json_is_reported(tree: tuple[Path, Path]) -> None:
    """JSON 语法错误应被报告而不是抛异常。"""
    config, assets = tree
    (config / "skills" / "broken.json").write_text("{oops", encoding="utf-8")
    errors = vc.validate(config, assets)
    assert any("JSON 解析失败" in e for e in errors)


def test_unknown_effect_stat_is_reported(tree: tuple[Path, Path]) -> None:
    """effect 使用未知属性名时应报错。"""
    config, assets = tree
    write_json(
        config / "skills" / "s3.json",
        {
            "id": "s3",
            "name": "S3",
            "type": "active",
            "effects": [{"stat": "luck", "mode": "add", "value": 1, "scope": "battle"}],
        },
    )
    errors = vc.validate(config, assets)
    assert any("未知 stat 'luck'" in e for e in errors)


def test_recipe_missing_material_is_reported(tree: tuple[Path, Path]) -> None:
    """配方引用不存在的材料时应报错。"""
    config, assets = tree
    write_json(
        config / "recipes" / "r1.json",
        {
            "id": "r1",
            "name": "R1",
            "kind": "pill",
            "inputs": {"ghost": 1},
            "effects": [],
        },
    )
    errors = vc.validate(config, assets)
    assert any("材料 'ghost' 不存在于 config/materials" in e for e in errors)


def test_mode_pool_reference_is_reported(tree: tuple[Path, Path]) -> None:
    """模式配置引用不存在的敌人时应报错。"""
    config, assets = tree
    write_json(
        config / "modes" / "tower.json",
        {"id": "tower", "name": "塔", "enemy_pool": ["ghost_enemy"]},
    )
    errors = vc.validate(config, assets)
    assert any("enemy_pool[0] 'ghost_enemy'" in e for e in errors)
