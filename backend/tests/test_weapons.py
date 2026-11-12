"""专属武器：解锁条件、唯一归属、装备与出发快照。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.config_loader import load_enemies, load_modes
from app.domain.run_engine import start_run
from app.domain.weapons import (
    battle_bonuses, combat_bonuses, craft_weapon, equip_weapon,
    unequip_weapon, weapon_views,
)
from app.models.save import DiscipleState, GameState, Resources

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)

TEMPLATES = {
    "t": {
        "id": "t", "name": "关羽", "lean": "attack", "rarity": 3,
        "base_stats": {"hp": 10, "atk": 3, "def": 2, "spd": 4},
    },
    "other": {
        "id": "other", "name": "张飞", "lean": "defense", "rarity": 2,
        "base_stats": {"hp": 12, "atk": 2, "def": 4, "spd": 3},
    },
}
MATERIALS = {
    "han_tie": {"id": "han_tie", "name": "寒铁"},
    "jiao_gu": {"id": "jiao_gu", "name": "蛟骨"},
}
WEAPONS = {
    "w1": {
        "id": "w1", "name": "青龙偃月刀", "template_id": "t",
        "inputs": {"han_tie": 2}, "stats": {"atk": .1, "hp": .1, "damage": .05},
        "unlock": {"floor": 8, "level": 3},
    },
    "w2": {
        "id": "w2", "name": "丈八蛇矛", "template_id": "t",
        "inputs": {"jiao_gu": 1}, "stats": {"def": .1, "shielding": .05},
        "unlock": {"floor": 8, "level": 3},
    },
}


def make_state(
    *, floor: int = 8, level: int = 3, **inventory: int,
) -> GameState:
    """构造满足专武解锁条件的存档。"""
    return GameState(
        resources=Resources(stamina=3),
        tower_floor=floor,
        inventory=dict(inventory),
        disciples=[
            DiscipleState(id="d1", template_id="t", level=level),
            DiscipleState(id="d2", template_id="other", level=level),
        ],
    )


def test_craft_requires_owned_disciple_floor_level_and_materials() -> None:
    """任一项不满足都拒绝锻造，且不扣材料。"""
    no_disciple = make_state(han_tie=2)
    no_disciple.disciples = []
    assert craft_weapon(no_disciple, "w1", WEAPONS, TEMPLATES, MATERIALS) == "尚未拥有该弟子"

    low_floor = make_state(floor=7, han_tie=2)
    assert "8 层" in (
        craft_weapon(low_floor, "w1", WEAPONS, TEMPLATES, MATERIALS) or ""
    )
    assert low_floor.inventory["han_tie"] == 2

    low_level = make_state(level=2, han_tie=2)
    assert "3 级" in (
        craft_weapon(low_level, "w1", WEAPONS, TEMPLATES, MATERIALS) or ""
    )

    no_material = make_state()
    assert "材料不足：寒铁" in (
        craft_weapon(no_material, "w1", WEAPONS, TEMPLATES, MATERIALS) or ""
    )


def test_craft_consumes_materials_and_rejects_duplicate() -> None:
    """锻造入行囊；行囊或已装备都算已拥有，不能重复获取。"""
    state = make_state(han_tie=3)

    assert craft_weapon(state, "w1", WEAPONS, TEMPLATES, MATERIALS) is None
    assert state.inventory["han_tie"] == 1
    assert state.inventory["w1"] == 1
    assert "已拥有" in (
        craft_weapon(state, "w1", WEAPONS, TEMPLATES, MATERIALS) or ""
    )
    assert state.inventory["han_tie"] == 1


def test_equip_wrong_owner_and_missing_stock_are_rejected() -> None:
    """专武只能给对应弟子，且必须先在行囊中。"""
    state = make_state()

    assert equip_weapon(state, "w1", "d2", WEAPONS) == "该专武不属于这名弟子"
    assert equip_weapon(state, "w1", "d1", WEAPONS) == "行囊中没有该专武"

    state.inventory["w1"] = 1
    assert equip_weapon(state, "w1", "d1", WEAPONS) is None
    assert "w1" in state.disciples[0].equipment
    assert "w1" not in state.inventory


def test_single_slot_requires_unequip_before_switching() -> None:
    """已有装备时必须先卸下，不能静默替换。"""
    state = make_state()
    state.disciples[0].equipment = ["w1"]
    state.inventory["w2"] = 1

    assert "先卸下" in (equip_weapon(state, "w2", "d1", WEAPONS) or "")
    assert state.inventory["w2"] == 1


def test_unequip_returns_weapon_to_inventory() -> None:
    """卸下后武器回到行囊，可以再次装备。"""
    state = make_state()
    state.disciples[0].equipment = ["w1"]

    assert unequip_weapon(state, "d1", WEAPONS) is None
    assert state.disciples[0].equipment == []
    assert state.inventory["w1"] == 1


def test_unknown_legacy_equipment_is_preserved() -> None:
    """旧档未知装备不提供加成，也不能被擅自删除。"""
    state = make_state()
    state.disciples[0].equipment = ["old_relic"]
    state.disciples[0].bonuses = {"atk": .05}

    assert unequip_weapon(state, "d1", WEAPONS) == "旧装备无法识别，暂不可卸下"
    assert state.disciples[0].equipment == ["old_relic"]
    assert combat_bonuses(state.disciples[0], {}, WEAPONS) == {"atk": .05}
    assert battle_bonuses(state.disciples[0], WEAPONS) == {}


def test_combat_bonuses_merge_global_personal_and_weapon() -> None:
    """宗门、个人与专武的基础属性相加；伤害类不进入基础属性。"""
    disciple = DiscipleState(
        id="d1", template_id="t", equipment=["w1"],
        bonuses={"atk": .05, "cultivation_rate": .1},
    )

    merged = combat_bonuses(disciple, {"atk": .05, "def": .02}, WEAPONS)

    assert merged["atk"] == pytest.approx(.2)
    assert merged["def"] == pytest.approx(.02)
    assert merged["hp"] == pytest.approx(.1)
    assert "damage" not in merged
    assert merged["cultivation_rate"] == pytest.approx(.1)
    assert battle_bonuses(disciple, WEAPONS) == {"damage": .05}


def test_run_snapshot_freezes_weapon_stats_and_ignores_later_changes() -> None:
    """出发快照固化专武加成，之后改配置或升级都不影响本局。"""
    state = make_state()
    state.disciples = [state.disciples[0]]
    state.disciples[0].equipment = ["w1"]

    weapons = {key: {**value, "stats": dict(value["stats"])} for key, value in WEAPONS.items()}
    assert start_run(
        state, ["d1"], TEMPLATES, load_modes()["tower"], NOW, seed=1,
        bonds={}, skills={}, enemies=load_enemies(), affix_pool=[], weapons=weapons,
    ) is None

    unit = state.active_run.party_snapshot.combatants[0]
    # 3 级成长 1.2，再叠加专武攻击 +10% 与气血 +10%。
    assert unit.attack == pytest.approx(3 * 1.2 * 1.1)
    assert unit.health == 13
    assert unit.bonuses == {"damage": .05}

    weapons["w1"]["stats"]["atk"] = 9
    state.disciples[0].level = 100
    weapons["w1"]["stats"]["damage"] = 9
    frozen = state.active_run.party_snapshot.combatants[0]
    assert frozen.attack == pytest.approx(3 * 1.2 * 1.1)
    assert frozen.bonuses == {"damage": .05}


def test_weapon_views_report_ownership_and_unmet_reasons() -> None:
    """列表同时给出归属与具体未满足条件。"""
    state = make_state(floor=7, level=2)
    views = {view.id: view for view in weapon_views(state, WEAPONS, TEMPLATES, MATERIALS)}
    assert "8 层" in views["w1"].reason
    assert views["w1"].craftable is False

    state.tower_floor = 8
    state.disciples[0].level = 3
    views = {view.id: view for view in weapon_views(state, WEAPONS, TEMPLATES, MATERIALS)}
    assert "材料不足" in views["w1"].reason

    state.inventory["w1"] = 1
    views = {view.id: view for view in weapon_views(state, WEAPONS, TEMPLATES, MATERIALS)}
    assert views["w1"].owned is True
    assert views["w1"].in_inventory is True
    assert views["w1"].reason == "已拥有该专武"

    state.disciples[0].equipment = ["w1"]
    state.inventory.pop("w1")
    views = {view.id: view for view in weapon_views(state, WEAPONS, TEMPLATES, MATERIALS)}
    assert views["w1"].equipped_by == "d1"
    assert views["w1"].in_inventory is False
