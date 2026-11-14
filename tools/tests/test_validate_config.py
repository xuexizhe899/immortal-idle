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
            "effects": [], "cooldown": 3, "vfx": "strike",
            "actions": [{"kind": "damage", "target": "enemy_first", "coefficient": 1.8}],
        },
    )
    write_json(
        config / "skills" / "p1.json",
        {
            "id": "p1",
            "name": "P1",
            "type": "passive",
            "effects": [], "bonuses": {"damage": .1}, "condition": "always",
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


def add_weapon_material(config: Path) -> None:
    """专武材料先落一份合法定义。"""
    write_json(
        config / "materials" / "han_tie.json",
        {"id": "han_tie", "name": "寒铁", "tier": 1},
    )


def write_weapon(config: Path, name: str, **changes: object) -> None:
    data = {
        "id": name,
        "name": "测试专武",
        "template_id": "d1",
        "inputs": {"han_tie": 1},
        "stats": {"atk": .1, "damage": .05},
        "unlock": {"floor": 8, "level": 3},
    }
    data.update(changes)
    write_json(config / "weapons" / f"{name}.json", data)


def test_valid_weapon_definition_is_accepted(tree: tuple[Path, Path]) -> None:
    """合法专武引用已有弟子、材料与已实现属性。"""
    config, assets = tree
    add_weapon_material(config)
    write_weapon(config, "w1")
    assert vc.validate(config, assets) == []


def test_weapon_rejects_missing_template_and_material(tree: tuple[Path, Path]) -> None:
    """弟子或材料引用不存在时必须报错。"""
    config, assets = tree
    write_weapon(config, "w1", template_id="ghost", inputs={"ghost": 1})
    errors = vc.validate(config, assets)
    assert any("template_id 'ghost' 不存在" in e for e in errors)
    assert any("材料 'ghost' 不存在" in e for e in errors)


def test_weapon_rejects_duplicate_template_and_bad_stats(tree: tuple[Path, Path]) -> None:
    """每名弟子只能有一把专武，属性只接受已实现乘区。"""
    config, assets = tree
    add_weapon_material(config)
    write_weapon(config, "w1")
    write_weapon(config, "w2", stats={"atk": .1, "luck": .2})
    errors = vc.validate(config, assets)
    assert any("每名弟子只能有一把" in e for e in errors)
    assert any("未实现属性 'luck'" in e for e in errors)


def test_pill_special_and_max_uses_are_validated(tree: tuple[Path, Path]) -> None:
    """未实现的丹药效果与非丹药次数上限必须报错。"""
    config, assets = tree
    write_json(config / "recipes" / "odd.json", {
        "id": "odd", "name": "怪丹", "kind": "pill",
        "inputs": {"han_tie": 1}, "effects": [], "special": "teleport",
    })
    write_json(config / "recipes" / "artifact.json", {
        "id": "artifact", "name": "法器", "kind": "artifact",
        "inputs": {"han_tie": 1}, "max_uses": 2,
        "effects": [{"stat": "atk", "mode": "add_pct", "value": .1, "scope": "permanent"}],
    })
    add_weapon_material(config)
    errors = vc.validate(config, assets)
    assert any("未实现的丹药效果 'teleport'" in e for e in errors)
    assert any("只有丹药可以设置 max_uses" in e for e in errors)


@pytest.mark.parametrize("action", [
    {"kind": "damage", "target": "enemy_first", "count": 7},
    {"kind": "damage", "target": "random_enemy"},
    {"kind": "damage", "target": "enemy_first", "coefficient": float("nan")},
    {"kind": "buff", "target": "all_allies", "stat": "hp", "value": .1},
    {"kind": "shield", "target": "ally_template", "coefficient": 2},
    {"kind": ["damage"], "target": {"name": "enemy_first"}},
    {"kind": "damage", "target": "enemy_first", "repeat": 100},
])
def test_invalid_combat_actions_are_rejected(tree, action):
    config, assets = tree
    patch(config / "skills" / "s1.json", actions=[action])
    assert any("config/skills/s1.json" in error for error in vc.validate(config, assets))


def test_duty_skills_and_unimplemented_pill_output_are_rejected(tree):
    config, assets = tree
    patch(config / "skills" / "p1.json", bonuses={"pill_rate": .1})
    assert any("未实现的属性 'pill_rate'" in error for error in vc.validate(config, assets))
    patch(config / "skills" / "p1.json", bonuses={"damage": .1}, effects=[
        {"stat": "cultivation_rate", "mode": "add_pct", "value": .1, "scope": "duty"},
    ])
    assert any("effects 必须为空" in error for error in vc.validate(config, assets))


@pytest.mark.parametrize("stat", ["atk", "def", "hp", "spd"])
@pytest.mark.parametrize("condition", ["shielded", "target_weakened", "first_round"])
def test_conditional_attributes_are_rejected_instead_of_silently_ignored(tree, stat, condition):
    config, assets = tree
    patch(config / "skills" / "p1.json", bonuses={stat: .1}, condition=condition)
    assert any("条件被动只支持" in error for error in vc.validate(config, assets))
    patch(config / "skills" / "p1.json", condition="always")
    assert vc.validate(config, assets) == []


def test_bond_modifier_requires_member_active_and_valid_extra_target(tree):
    config, assets = tree
    write_json(config / "bonds" / "bond.json", {
        "id": "bond", "name": "羁绊", "members": ["d1"], "requires": 1, "effects": [],
        "modifiers": [{"skill": "p1", "extra_actions": [{
            "kind": "shield", "target": "ally_template", "target_template": "ghost", "coefficient": 1,
        }]}],
    })
    errors = vc.validate(config, assets)
    assert any("主动技能" in error for error in errors)
    assert any("必须是羁绊成员" in error for error in errors)


def test_enemy_encounter_requires_real_templates_and_at_most_six_units(tree):
    config, assets = tree
    write_json(config / "modes" / "tower.json", {
        "id": "tower", "name": "塔", "enabled": True,
        "encounters": {"battle": ["ghost"], "elite": ["ghost"] * 7, "boss": []},
    })
    errors = vc.validate(config, assets)
    assert any("敌人 'ghost' 不存在" in error for error in errors)
    assert sum("敌方需要 1..6 人" in error for error in errors) == 2


def test_enemy_encounter_variants_and_multipliers_are_validated(tree):
    config, assets = tree
    write_json(config / "enemies" / "guard.json", {
        "id": "guard", "name": "守卫", "base_stats": {"hp": 10, "atk": 1, "def": 1, "spd": 1},
    })
    write_json(config / "modes" / "tower.json", {
        "id": "tower", "name": "塔", "enabled": True,
        "encounters": {"battle": ["guard"], "elite": ["guard"], "boss": ["guard"]},
        "kind_stat_multiplier": {"battle": 1, "elite": 4, "boss": 1},
        "encounter_variants": {
            "battle": [["guard"], ["ghost"]],
            "elite": [["guard"] * 7],
            "event": [["guard"]],
        },
    })
    errors = vc.validate(config, assets)
    assert any("kind_stat_multiplier.elite" in error for error in errors)
    assert any("敌人 'ghost' 不存在" in error for error in errors)
    assert any("敌方需要 1..6 人" in error for error in errors)
    assert any("未知类型 'event'" in error for error in errors)


def test_route_reward_bounds_are_validated(tree):
    config, assets = tree
    write_json(config / "modes" / "tower.json", {
        "id": "tower", "name": "塔", "route_reward_min": .85, "route_reward_max": 1.3,
    })
    assert vc.validate(config, assets) == []

    patch(config / "modes" / "tower.json", route_reward_max=None)
    errors = vc.validate(config, assets)
    assert any("必须同时配置" in error for error in errors)

    patch(config / "modes" / "tower.json", route_reward_min=.4, route_reward_max=1.6)
    errors = vc.validate(config, assets)
    assert any("route_reward_min/max" in error for error in errors)


def test_invalid_enemy_stats_and_embedded_skill_are_rejected(tree):
    config, assets = tree
    write_json(config / "enemies" / "guard.json", {
        "id": "guard", "name": "守卫", "base_stats": {"hp": 10, "atk": -1, "def": 1, "spd": 1},
        "skill": {"id": "guard-hit", "name": "攻击", "type": "active", "effects": [], "cooldown": 0, "vfx": "strike", "actions": []},
    })
    errors = vc.validate(config, assets)
    assert any("base_stats.atk" in error for error in errors)
    assert any("cooldown" in error for error in errors)


@pytest.fixture()
def city_tree(tree: tuple[Path, Path]) -> tuple[Path, Path]:
    """独立验证完整背景与可选建筑 sprite 两种主城布局。"""
    config, assets = tree
    (assets / "city").mkdir()
    (assets / "city" / "complete.png").write_bytes(b"PNG")
    (assets / "city" / "tower.png").write_bytes(b"PNG")
    write_json(config / "ui" / "city.json", {
        "background": "/assets/city/complete.png", "aspect": 1.5,
        "hotspots": [{
            "id": "tower", "name": "问道塔", "panel": "tower",
            "x": 50, "y": 50, "w": 20, "h": 40,
        }],
    })
    return config, assets


def edit_hotspot(config: Path, **changes: object) -> None:
    path = config / "ui" / "city.json"
    city = json.loads(path.read_text(encoding="utf-8"))
    city["hotspots"][0].update(changes)
    write_json(path, city)


def test_city_background_and_optional_sprite_are_validated(city_tree):
    config, assets = city_tree
    assert vc.validate(config, assets) == []
    edit_hotspot(config, sprite="/assets/city/tower.png")
    assert vc.validate(config, assets) == []
    (assets / "city" / "tower.png").unlink()
    assert any("hotspots[0].sprite: 本地资产不存在" in error for error in vc.validate(config, assets))


def test_city_missing_background_reports_asset_path(city_tree):
    config, assets = city_tree
    (assets / "city" / "complete.png").unlink()
    errors = vc.validate(config, assets)
    assert any("background: 本地资产不存在 '/assets/city/complete.png'" in error for error in errors)


@pytest.mark.parametrize("background", [
    "https://example.com/city.png", "/assets/../../outside.png", "/assets/city/complete.png?v=1",
])
def test_city_rejects_remote_or_escaping_asset_paths(city_tree, background):
    config, assets = city_tree
    patch(config / "ui" / "city.json", background=background)
    assert any("background:" in error for error in vc.validate(config, assets))


def test_city_duplicate_hotspot_id_and_unknown_panel_are_reported(city_tree):
    config, assets = city_tree
    path = config / "ui" / "city.json"
    city = json.loads(path.read_text(encoding="utf-8"))
    city["hotspots"].append({**city["hotspots"][0], "panel": "storage"})
    write_json(path, city)
    errors = vc.validate(config, assets)
    assert any("id 'tower' 重复" in error for error in errors)
    assert any("hotspots[1]: panel" in error for error in errors)


@pytest.mark.parametrize(("key", "value"), [
    ("x", float("nan")), ("y", float("inf")), ("w", True),
    ("h", 0), ("x", -1), ("y", 101), ("w", 101), ("h", "20"),
])
def test_city_rejects_nonfinite_or_invalid_percentages(city_tree, key, value):
    config, assets = city_tree
    edit_hotspot(config, **{key: value})
    assert any(f"hotspots[0].{key}:" in error for error in vc.validate(config, assets))


def test_city_rejects_hotspot_extending_outside_background(city_tree):
    config, assets = city_tree
    edit_hotspot(config, x=3, w=20)
    assert any("热区边界" in error for error in vc.validate(config, assets))


def test_city_malformed_json_is_reported_without_crashing(city_tree):
    config, assets = city_tree
    (config / "ui" / "city.json").write_text("{oops", encoding="utf-8")
    assert any("config/ui/city.json: JSON 读取失败" in error for error in vc.validate(config, assets))


def add_economy_config(config: Path) -> None:
    """用最小已有材料补齐新设施，保留其他旧夹具不变。"""
    write_json(config / "materials" / "han_tie.json", {"id": "han_tie", "name": "寒铁", "tier": 1})
    patch(config / "disciples" / "d1.json", production_specialty="han_tie")
    write_json(config / "facilities.json", {
        key: {"name": key, "descriptions": ["一级", "二级", "三级"], "costs": [{"han_tie": 2}, {"spirit_stone": 3}]}
        for key in ("hall", "forge", "alchemy", "tower", "training")
    })


def test_facilities_and_specialty_are_optional_for_old_tree_and_valid_for_new_tree(tree):
    config, assets = tree
    assert vc.validate(config, assets) == []
    add_economy_config(config)
    assert vc.validate(config, assets) == []


@pytest.mark.parametrize("value", [None, "missing", ["han_tie"]])
def test_new_content_requires_one_existing_production_specialty(tree, value):
    config, assets = tree
    add_economy_config(config)
    patch(config / "disciples" / "d1.json", production_specialty=value)
    assert any("production_specialty" in error for error in vc.validate(config, assets))


@pytest.mark.parametrize("cost", [{"ghost": 1}, {"han_tie": -1}, {"han_tie": 1.5}, {"spirit_stone": float("nan")}, {"spirit_stone": True}])
def test_facility_costs_reject_missing_resources_and_invalid_amounts(tree, cost):
    config, assets = tree
    add_economy_config(config)
    path = config / "facilities.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["forge"]["costs"][0] = cost
    write_json(path, data)
    assert any("facilities.json.forge.costs[0]" in error for error in vc.validate(config, assets))


def test_facilities_reject_incomplete_level_data_and_malformed_json(tree):
    config, assets = tree
    add_economy_config(config)
    path = config / "facilities.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["forge"]["costs"] = []
    data["alchemy"]["descriptions"] = ["一级"]
    write_json(path, data)
    errors = vc.validate(config, assets)
    assert any("forge.costs" in error for error in errors)
    assert any("alchemy.descriptions" in error for error in errors)
    path.write_text("{broken", encoding="utf-8")
    assert any("facilities.json: JSON 读取失败" in error for error in vc.validate(config, assets))


def minimal_sects():
    return {
        "name_prefixes": ["云"], "level_names": ["下院", "内院", "上宗"], "level_scales": [1, 2, 3],
        "styles": [{"id": f"style{i}", "name": "流派", "suffix": "宗", "materials": ["ore", "ore", "ore"],
                    "special_material": "rare", "leader": "guard", "teams": [["guard"] * 3]} for i in range(3)],
    }


def test_sect_combinations_validate_enemy_and_material_references(tmp_path):
    data = minimal_sects()
    write_json(tmp_path / "sects.json", data)
    errors = []
    vc.check_sects(tmp_path, {"ore": {}, "rare": {}}, {"guard": {}}, errors)
    assert errors == []
    data["styles"][0]["teams"][0][1] = "ghost"
    data["styles"][1]["special_material"] = "missing"
    data["styles"][2]["leader"] = []
    write_json(tmp_path / "sects.json", data)
    vc.check_sects(tmp_path, {"ore": {}, "rare": {}}, {"guard": {}}, errors)
    assert any("敌人 'ghost'" in error for error in errors)
    assert any("special_material" in error for error in errors)
    assert any("leader" in error for error in errors)


def test_sects_reject_wrong_roster_size_duplicate_style_and_nonfinite_scale(tmp_path):
    data = minimal_sects()
    data["styles"][1]["id"] = data["styles"][0]["id"]
    data["styles"][0]["teams"] = [["guard"]]
    data["level_scales"][2] = float("inf")
    write_json(tmp_path / "sects.json", data)
    errors = []
    vc.check_sects(tmp_path, {"ore": {}, "rare": {}}, {"guard": {}}, errors)
    assert any("重复" in error for error in errors)
    assert any("每组守军必须为三人" in error for error in errors)
    assert any("level_scales" in error for error in errors)


@pytest.mark.parametrize("data", [[], {"styles": [1]}, {"styles": []}])
def test_sects_malformed_structure_is_reported_without_crashing(tmp_path, data):
    write_json(tmp_path / "sects.json", data)
    errors = []
    vc.check_sects(tmp_path, {}, {}, errors)
    assert errors
