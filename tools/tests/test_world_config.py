"""世界配置的引用与可执行边界。"""

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import validate_config as vc  # noqa: E402


@pytest.fixture
def world_tree(tmp_path):
    data = json.loads((vc.CONFIG_DIR / "world.json").read_text(encoding="utf-8"))
    materials = {path.stem: {} for path in (vc.CONFIG_DIR / "materials").glob("*.json")}
    materials[data["ascension_token"]] = {}
    enemies = {path.stem: {} for path in (vc.CONFIG_DIR / "enemies").glob("*.json")}
    return tmp_path, data, materials, enemies


def check(tree, data=None):
    folder, original, materials, enemies = tree
    (folder / "world.json").write_text(json.dumps(data or original, ensure_ascii=False), encoding="utf-8")
    errors = []
    vc.check_world(folder, materials, enemies, errors)
    return errors


def test_real_world_configuration_is_valid(world_tree):
    assert check(world_tree) == []


@pytest.mark.parametrize("key,value", [
    ("hours_per_wave", 0), ("pending_cap", True), ("initial_pending", 4),
    ("wave_growth", -1), ("wave_scale_cap", .5),
])
def test_invalid_invasion_limits_are_reported(world_tree, key, value):
    data = deepcopy(world_tree[1])
    data["invasion"][key] = value
    assert any(key in error for error in check(world_tree, data))


def test_world_references_are_checked(world_tree):
    data = deepcopy(world_tree[1])
    data["ascension_token"] = "missing_token"
    area = data["regions"][0]["areas"][0]
    area["boss"] = ["missing_enemy"]
    area["first_reward"] = {"missing_material": 1}
    area["dungeons"][0]["slot"] = "helmet"
    errors = check(world_tree, data)
    assert any("ascension_token" in item for item in errors)
    assert any("boss" in item for item in errors)
    assert any("missing_material" in item for item in errors)
    assert any("dungeons" in item for item in errors)


def test_missing_region_or_area_is_not_treated_as_complete_content(world_tree):
    data = deepcopy(world_tree[1])
    data["regions"] = data["regions"][:1]
    assert any("两个完整地区" in item for item in check(world_tree, data))
    data = deepcopy(world_tree[1])
    data["regions"][0]["areas"] = []
    assert any("三个片区" in item for item in check(world_tree, data))


def test_region_and_area_identifiers_cannot_skip_or_repeat(world_tree):
    data = deepcopy(world_tree[1])
    data["regions"][1]["id"] = 4
    data["regions"][0]["areas"][1]["id"] = 1
    errors = check(world_tree, data)
    assert any("地区编号" in item for item in errors)
    assert any("片区编号" in item for item in errors)


def test_map_and_legacy_tower_cost_must_match(world_tree):
    folder, data, materials, enemies = world_tree
    data["tower_stamina_cost"] = 2
    (folder / "world.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    errors = []
    vc.check_world(folder, materials, enemies, errors, {"tower": {"stamina_cost": 1}})
    assert any("行动力成本一致" in item for item in errors)
