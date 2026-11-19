"""装备配置的随机池、数值范围和材料引用校验。"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import validate_config as vc  # noqa: E402


def check(tmp_path, data):
    (tmp_path / "equipment.json").write_text(json.dumps(data), encoding="utf-8")
    errors = []
    vc.check_equipment(tmp_path, {"lian_qi_jing_cui": {}}, errors)
    return errors


def config():
    return json.loads((Path(__file__).resolve().parents[2] / "config/equipment.json").read_text(encoding="utf-8"))


def test_current_equipment_config_and_personal_yield_affixes_are_supported(tmp_path):
    data = config()
    data["affix_pools"]["ring"].append("cultivation_rate")
    assert check(tmp_path, data) == []


@pytest.mark.parametrize(("field", "value"), [
    ("material", "missing"), ("upgrade_base_cost", 0), ("reforge_base_cost", True),
    ("growth_per_level", float("inf")), ("tier_growth", -1),
    ("affix_grades", [.02, .06]), ("affix_grades", [.06, .04, .02]),
    ("affix_pools", {"weapon": []}), ("definitions", []),
])
def test_invalid_costs_or_pools_are_rejected(tmp_path, field, value):
    data = config()
    data[field] = value
    assert any(field in error for error in check(tmp_path, data))


def test_missing_slot_and_invalid_definition_are_reported(tmp_path):
    data = config()
    data["definitions"] = [{"id": "item", "name": "物品", "slot": "weapon", "stat": "unknown", "value": 0}]
    errors = check(tmp_path, data)
    assert any(".stat" in error for error in errors)
    assert any(".value" in error for error in errors)
    assert any("四个装备槽都必须" in error for error in errors)
