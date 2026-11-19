"""个人装备实例、独立随机序列、付费原子性与旧档迁移回归。"""

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app.config_loader import load_equipment, load_recipes
from app.domain.equipment import (
    combat_equipment_bonuses, equip_gear, equipment_stats, gear_views, grant_drop,
    migrate_equipment, reforge_gear, resolve_reforge, roll_drop, smelt_gear,
    smelt_yield, unequip_gear, upgrade_gear,
)
from app.domain.rng import Pcg32
from app.domain.training import preview
from app.domain.weapons import equip_weapon
from app.models.equipment import GearAffix, GearItem
from app.models.save import ActiveRun, DiscipleState, GameState, Resources

NOW = datetime(2026, 11, 19, tzinfo=timezone.utc)
MATERIAL = "lian_qi_jing_cui"


def make_state() -> GameState:
    return GameState(
        rng_seed=13, equipment_version=1, inventory={MATERIAL: 100},
        disciples=[DiscipleState(id="d1", template_id="t"), DiscipleState(id="d2", template_id="t")],
    )


def add_item(state: GameState, item_id="item", slot="weapon", **changes) -> GearItem:
    item = GearItem(
        **{"id": item_id, "definition_id": "test", "name": "测试装备", "slot": slot,
           "main_stat": "atk", "main_value": .1, **changes},
    )
    state.gear[item.id] = item
    return item


def test_drop_is_replayable_and_reload_keeps_each_instance():
    config = deepcopy(load_equipment())
    config["definitions"] = [config["definitions"][0]]
    config["growth_per_level"] = .25
    first, replay = make_state(), make_state()
    rng, same_rng = Pcg32(17), Pcg32(17)
    items = [grant_drop(first, rng, 2, "weapon", config=config) for _ in range(2)]
    repeated = [grant_drop(replay, same_rng, 2, "weapon", config=config) for _ in range(2)]
    assert items == repeated
    assert items[0].name == items[1].name
    assert items[0].id != items[1].id
    assert all(item.growth_per_level == .25 for item in items)
    assert all(item.affix_grade in (1, 2, 3) for item in items)
    restored = GameState.model_validate_json(first.model_dump_json())
    assert restored.gear == first.gear
    assert restored.next_gear_id == 3
    assert rng.cursor == same_rng.cursor


def test_run_drop_is_reserved_but_not_available_before_settlement():
    state = make_state()
    state.active_run = ActiveRun(run_seed=2, started_at=NOW)
    pending = roll_drop(state, Pcg32(2), 1, "armor", config=load_equipment())
    state.active_run.pending_gear.append(pending)
    assert state.gear == {}
    assert equip_gear(state, pending.id, "d1") == "装备不存在"
    assert smelt_gear(state, pending.id, load_equipment())
    state.next_gear_id = 1
    next_item = roll_drop(state, Pcg32(2), 1, "armor", config=load_equipment())
    assert next_item.id != pending.id
    restored = GameState.model_validate_json(state.model_dump_json())
    assert restored.active_run.pending_gear == [pending]


def test_four_slots_are_personal_and_transfer_does_not_copy_effects():
    state = make_state()
    for slot in ("weapon", "armor", "boots", "ring"):
        add_item(state, slot, slot)
        assert equip_gear(state, slot, "d1") is None
    assert combat_equipment_bonuses(state, state.disciples[0]) == pytest.approx({"atk": .4})
    assert combat_equipment_bonuses(state, state.disciples[1]) == {}
    assert state.bonuses == {}
    assert equip_gear(state, "weapon", "d2") is None
    assert "weapon" not in state.disciples[0].gear_slots
    assert combat_equipment_bonuses(state, state.disciples[0]) == pytest.approx({"atk": .3})
    assert combat_equipment_bonuses(state, state.disciples[1]) == {"atk": .1}
    assert unequip_gear(state, "weapon") is None
    assert combat_equipment_bonuses(state, state.disciples[1]) == {}


def test_replacing_same_slot_keeps_old_item_and_special_weapon_is_exclusive():
    state = make_state()
    add_item(state, "old")
    add_item(state, "new")
    assert equip_gear(state, "old", "d1") is None
    assert equip_gear(state, "new", "d1") is None
    assert state.disciples[0].gear_slots == {"weapon": "new"}
    assert set(state.gear) == {"old", "new"}
    state.inventory["exclusive"] = 1
    weapons = {"exclusive": {"template_id": "t"}}
    before = state.model_dump()
    assert equip_weapon(state, "exclusive", "d1", weapons) == "请先卸下当前武器"
    assert state.model_dump() == before
    assert unequip_gear(state, "new") is None
    assert equip_weapon(state, "exclusive", "d1", weapons) is None
    assert equip_gear(state, "new", "d1") == "请先卸下当前专武"


@pytest.mark.parametrize("action", ["equip", "unequip", "upgrade", "reforge", "resolve"])
def test_run_members_cannot_modify_equipment(action):
    state = make_state()
    item = add_item(state)
    state.disciples[0].gear_slots = {"weapon": item.id}
    state.active_run = ActiveRun(run_seed=1, party=["d1"], started_at=NOW)
    item.pending_affix = GearAffix(stat="hp", grade=1, value=.02)
    before = state.model_dump()
    commands = {
        "equip": lambda: equip_gear(state, item.id, "d2"),
        "unequip": lambda: unequip_gear(state, item.id),
        "upgrade": lambda: upgrade_gear(state, item.id, load_equipment()),
        "reforge": lambda: reforge_gear(state, item.id, load_equipment()),
        "resolve": lambda: resolve_reforge(state, item.id, False),
    }
    assert "出征" in commands[action]()
    assert state.model_dump() == before


@pytest.mark.parametrize("slot", ["weapon", "armor", "boots", "ring"])
def test_every_slot_upgrades_with_real_cost_and_facility_cap(slot):
    state = make_state()
    item = add_item(state, slot=slot, growth_per_level=.25, affix="hp", affix_value=.06)
    config = load_equipment()
    for _ in range(3):
        listed = gear_views(state, config)[0]
        assert listed.upgradeable
        expected = listed.upgrade_stats
        assert upgrade_gear(state, item.id, config) is None
        assert equipment_stats(item) == expected
    assert equipment_stats(item) == {"atk": .175, "hp": .06}
    assert item.invested == {MATERIAL: 12}
    assert state.inventory[MATERIAL] == 88
    before = state.model_dump()
    assert "上限" in upgrade_gear(state, item.id, config)
    assert state.model_dump() == before
    state.facility_levels["forge"] = 2
    assert upgrade_gear(state, item.id, config) is None
    assert item.level == 4
    assert item.invested[MATERIAL] == 20


def test_failed_upgrade_or_reforge_does_not_spend_resources_or_rng():
    state = make_state()
    item = add_item(state)
    state.inventory.clear()
    before = state.model_dump()
    assert upgrade_gear(state, item.id, load_equipment()) == "炼器精粹不足"
    assert reforge_gear(state, item.id, load_equipment()) == "炼器精粹不足"
    assert state.model_dump() == before


def test_reforge_pays_once_and_pending_choice_survives_reload():
    state = make_state()
    item = add_item(state, level=2, affix="hp", affix_grade=1, affix_value=.02)
    before_id = state.next_gear_id
    assert reforge_gear(state, item.id, load_equipment()) is None
    assert state.gear_rng_cursor == 4
    assert state.next_gear_id == before_id
    assert state.inventory[MATERIAL] == 97
    assert item.invested == {}
    pending = item.pending_affix.model_dump()
    restored = GameState.model_validate_json(state.model_dump_json())
    assert restored.gear[item.id].pending_affix.model_dump() == pending
    before = restored.model_dump()
    assert "先选择" in reforge_gear(restored, item.id, load_equipment())
    assert "先选择" in upgrade_gear(restored, item.id, load_equipment())
    assert restored.model_dump() == before
    assert resolve_reforge(restored, item.id, True) is None
    assert restored.gear[item.id].affix == "hp"
    assert restored.inventory[MATERIAL] == 97
    assert reforge_gear(restored, item.id, load_equipment()) is None
    candidate = restored.gear[item.id].pending_affix
    assert restored.gear_rng_cursor == 6
    assert resolve_reforge(restored, item.id, False) is None
    changed = restored.gear[item.id]
    assert (changed.affix, changed.affix_grade, changed.affix_value) == (candidate.stat, candidate.grade, candidate.value)
    assert changed.level == 2 and changed.main_value == .1
    assert changed.pending_affix is None
    assert resolve_reforge(restored, item.id, False) == "没有待选择的洗练结果"


def test_reforge_stream_replays_independently_from_run_and_item_ids():
    left, right = make_state(), make_state()
    add_item(left)
    add_item(right)
    left.active_run = ActiveRun(run_seed=91, rng_cursor=17, party=["d2"], started_at=NOW)
    right.active_run = ActiveRun(run_seed=9, rng_cursor=43, party=["d2"], started_at=NOW)
    right.next_gear_id = 999
    for _ in range(3):
        assert reforge_gear(left, "item", load_equipment()) is None
        assert reforge_gear(right, "item", load_equipment()) is None
        assert left.gear["item"].pending_affix == right.gear["item"].pending_affix
        assert left.gear_rng_cursor == right.gear_rng_cursor
        assert resolve_reforge(left, "item", False) is None
        assert resolve_reforge(right, "item", False) is None
    assert right.next_gear_id == 999
    assert left.rng_seed == right.rng_seed == 13
    assert left.active_run.rng_cursor == 17
    assert right.active_run.rng_cursor == 43


@pytest.mark.parametrize("blocker", ["equipped", "locked", "pending"])
def test_smelt_rejects_protected_equipment_without_granting_materials(blocker):
    state = make_state()
    item = add_item(state)
    if blocker == "equipped":
        state.disciples[0].gear_slots = {"weapon": item.id}
    elif blocker == "locked":
        item.locked = True
    else:
        item.pending_affix = GearAffix(stat="hp", grade=1, value=.02)
    before = state.model_dump()
    assert smelt_gear(state, item.id, load_equipment())
    assert gear_views(state, load_equipment())[0].smelt_reason
    assert state.model_dump() == before


def test_smelt_returns_eighty_percent_of_each_investment_once():
    state = make_state()
    item = add_item(state, invested={MATERIAL: 7, "han_tie": 3})
    expected = {MATERIAL: 7, "han_tie": 2}
    assert smelt_yield(item, load_equipment()) == expected
    assert gear_views(state, load_equipment())[0].smelt_returns == expected
    assert smelt_gear(state, item.id, load_equipment()) is None
    assert state.inventory == {MATERIAL: 107, "han_tie": 2}
    before = state.model_dump()
    assert smelt_gear(state, item.id, load_equipment())
    assert state.model_dump() == before
    state.inventory["exclusive"] = 1
    assert "专武" in smelt_gear(state, "exclusive", load_equipment())
    assert state.inventory["exclusive"] == 1


def test_legacy_migration_preserves_unexplained_bonuses_and_run_snapshot():
    recipes = load_recipes()
    state = make_state()
    state.equipment_version = 0
    state.crafted_recipes = ["qing_feng_jian", "ju_ling_pei", "unknown", "qing_feng_jian"]
    state.recipe_levels = {"qing_feng_jian": 2}
    state.bonuses = {"atk": .32, "cultivation_rate": .25, "custom": -.1}
    state.disciples[0].bonuses = {"atk": .13}
    state.active_run = ActiveRun(run_seed=9, party=["d1"], started_at=NOW)
    before_run = state.active_run.model_dump()
    migrate_equipment(state, recipes)
    assert state.equipment_version == 1
    assert state.bonuses == pytest.approx({"atk": .2, "cultivation_rate": .1, "custom": -.1})
    assert state.disciples[0].bonuses == {"atk": .13}
    assert state.active_run.model_dump() == before_run
    assert "unknown" in state.crafted_recipes
    assert len(state.gear) == 2
    sword = next(item for item in state.gear.values() if item.slot == "weapon")
    assert sword.main_value == pytest.approx(.12)
    assert sword.invested == {key: value * 3 for key, value in recipes["qing_feng_jian"]["inputs"].items()}
    before = state.model_dump()
    migrate_equipment(state, recipes)
    assert state.model_dump() == before


def test_legacy_migration_does_not_remove_negative_or_missing_bonus():
    state = GameState(crafted_recipes=["qing_feng_jian"], bonuses={"atk": -.1})
    migrate_equipment(state, load_recipes())
    assert state.bonuses == {"atk": -.1}
    assert state.gear == {}


def test_training_preview_includes_only_this_disciples_equipment():
    state = make_state()
    state.resources = Resources(cultivation=100, spirit_stone=100)
    state.bonuses = {"atk": .1}
    state.disciples[0].bonuses = {"atk": .05}
    item = add_item(state, main_value=.2)
    equip_gear(state, item.id, "d1")
    ring = add_item(state, "ring", "ring", main_stat="cultivation_rate", main_value=.5)
    equip_gear(state, ring.id, "d1")
    template = {"lean": "attack", "rarity": 1, "base_stats": {"hp": 20, "atk": 10, "def": 5, "spd": 4}}
    before = state.model_dump()
    result = preview(state, state.disciples[0], template, {}, {})
    assert result.current.attack == 13.5
    assert result.current.duty_rates["cultivation_rate"] == .075
    assert result.next_level.target.attack == 14.85
    assert preview(state, state.disciples[1], template, {}, {}).current.attack == 11
    assert state.model_dump() == before


def test_training_preview_continues_growth_after_ascending_and_returning_to_old_region():
    state = make_state()
    disciple = state.disciples[0]
    disciple.level, disciple.realm = 10, 3
    state.resources = Resources(cultivation=1000, spirit_stone=1000, reputation=1000)
    template = {"lean": "attack", "rarity": 1, "base_stats": {"hp": 20, "atk": 10, "def": 5, "spd": 4}}
    assert not preview(state, disciple, template, {}, {}).next_realm.allowed
    state.world.unlocked_regions = [1, 2]
    state.world.current_region = 1
    result = preview(state, disciple, template, {}, {})
    assert result.max_realm == 6
    assert result.next_realm.allowed
    assert result.next_realm.requires_level == 10
    disciple.realm = 4
    result = preview(state, disciple, template, {}, {})
    assert result.level_cap == 13
    assert result.next_level.allowed
    disciple.realm, disciple.level = 6, 20
    result = preview(state, disciple, template, {}, {})
    assert result.level_cap == 20
    assert not result.next_level.allowed and not result.next_realm.allowed
