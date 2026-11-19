"""飞升后的宗门、个人成长与宗主掉装；全部使用内存测试档。"""

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app.config_loader import (
    load_bonds, load_disciples, load_enemies, load_facilities, load_modes, load_sects, load_world,
)
from app.domain import conquest
from app.domain.facilities import facility_views
from app.domain.progression import breakthrough, growth_caps, level_cap, upgrade
from app.domain.run_engine import party_power, settle_run, start_run
from app.models.save import DiscipleState, DutySlot, GameState, Resources

NOW = datetime(2026, 11, 19, tzinfo=timezone.utc)
PARTY = ["guanyu", "zhangfei", "zhaoyun", "zhugeliang", "yuefei", "baisuzhen"]


def ensure(state, world=True):
    return conquest.ensure_sects(state, load_sects(), load_enemies(), load_world() if world else None)


def test_unlocking_second_region_adds_distinct_sects_without_rerolling_old_sects():
    state = GameState(rng_seed=71, facility_levels={"hall": 3})
    ensure(state)
    state.sects[0].conquered = True
    state.sects[0].garrison = [DutySlot(disciple_id="guard", assigned_at=NOW)]
    original = deepcopy(state.sects)
    state.world.unlocked_regions.append(2)
    assert ensure(state)
    assert len(state.sects) == 18 and state.sects[:9] == original
    second = state.sects[9:]
    assert [sect.id for sect in second] == [f"r2:sect_{index}" for index in range(1, 10)]
    assert [sect.area for sect in second] == [1] * 3 + [2] * 3 + [3] * 3
    assert all(sect.region_id == 2 for sect in second)
    for old, new in zip(original, second):
        assert new.leader.attack == pytest.approx(old.leader.attack * 3.2)
        assert new.loot == {key: value * 2.5 for key, value in old.loot.items()}
    restored = GameState.model_validate_json(state.model_dump_json())
    assert not ensure(restored)
    assert restored == state


def test_each_regions_hall_gate_remains_three_six_nine_without_repeated_generation():
    state = GameState(rng_seed=12)
    state.world.unlocked_regions = [1, 2]
    for hall, expected in ((1, 6), (2, 12), (3, 18)):
        state.facility_levels["hall"] = hall
        assert ensure(state)
        assert len(state.sects) == expected
        assert not ensure(state)


def test_legacy_generation_and_new_generation_keep_first_region_identity_and_combat_inputs():
    legacy = GameState(rng_seed=71, facility_levels={"hall": 3})
    modern = GameState(rng_seed=71, facility_levels={"hall": 3})
    ensure(legacy, False)
    ensure(modern)
    assert legacy.sects == modern.sects
    original = deepcopy(legacy.sects[3])
    legacy.sects[3].area = 1
    assert ensure(legacy)
    assert legacy.sects[3] == original


def make_growth_state():
    return GameState(
        resources=Resources(cultivation=100000, spirit_stone=100000, reputation=100000),
        disciples=[DiscipleState(id="g", template_id="guanyu", level=10, realm=3)],
    )


def test_second_region_growth_opens_only_after_ascension_and_keeps_existing_levels():
    state = make_growth_state()
    disciple = state.disciples[0]
    assert growth_caps(state) == (10, 3)
    assert "最高境界" in breakthrough(state, "g", load_disciples())[1]
    before_power = party_power([disciple], load_disciples())
    state.world.unlocked_regions.append(2)
    assert growth_caps(state) == (20, 6)
    costs, error = breakthrough(state, "g", load_disciples())
    assert error is None and costs == {"reputation": 220}
    assert disciple.realm == 4 and disciple.level == 10
    assert party_power([disciple], load_disciples()) > before_power
    costs, error = upgrade(state, "g")
    assert error is None and costs == {"cultivation": 200, "spirit_stone": 100}
    assert disciple.level == 11


def test_second_region_reaches_realm_six_level_twenty_and_retains_caps_on_old_map():
    state = make_growth_state()
    state.world.unlocked_regions = [1, 2]
    state.world.current_region = 1
    disciple = state.disciples[0]
    assert [level_cap(realm) for realm in range(1, 7)] == [3, 6, 10, 13, 16, 20]
    for realm in (4, 5, 6):
        assert breakthrough(state, "g", load_disciples())[1] is None
        assert disciple.realm == realm
        while disciple.level < level_cap(realm):
            assert upgrade(state, "g")[1] is None
    before = state.model_dump_json()
    assert "等级上限 20" in upgrade(state, "g")[1]
    assert "最高境界" in breakthrough(state, "g", load_disciples())[1]
    assert state.model_dump_json() == before


def test_later_realm_level_requirement_and_reputation_failure_do_not_spend():
    state = make_growth_state()
    state.world.unlocked_regions = [1, 2]
    disciple = state.disciples[0]
    disciple.realm = 4
    before = state.model_dump_json()
    assert "13 级" in breakthrough(state, "g", load_disciples())[1]
    assert state.model_dump_json() == before
    disciple.level = 13
    state.resources.reputation = 0
    before = state.model_dump_json()
    assert "声望不足" in breakthrough(state, "g", load_disciples())[1]
    assert state.model_dump_json() == before


def make_boss_run(legacy=False):
    state = GameState(rng_seed=71, resources=Resources(stamina=6), disciples=[
        DiscipleState(id=key, template_id=key, level=20, realm=6) for key in PARTY
    ])
    ensure(state)
    state.sects[0].conquered = True
    assert start_run(
        state, PARTY, load_disciples(), load_modes()["expedition"], NOW,
        seed=18, bonds=load_bonds(), sect=state.sects[0], route_version=2,
        is_retrial=True, retrial_reward={"spirit_stone": 10},
    ) is None
    if legacy:
        mode = deepcopy(state.active_run.party_snapshot.mode)
        mode.pop("equipment_rules")
        state.active_run.party_snapshot = state.active_run.party_snapshot.model_copy(update={"mode": mode})
    return state


def test_sect_boss_drops_one_frozen_item_and_settlement_delivers_once():
    state = make_boss_run()
    restored = GameState.model_validate_json(state.model_dump_json())
    for current in (state, restored):
        before_cursor = current.active_run.rng_cursor
        assert conquest.arena(current, PARTY[:3]) is None
        assert current.active_run.last_battle.won
        assert len(current.active_run.pending_gear) == 1
        assert current.active_run.rng_cursor > before_cursor
        before = current.model_dump_json()
        assert "已结束" in conquest.arena(current, PARTY[:3])
        assert current.model_dump_json() == before
    assert state.active_run.pending_gear == restored.active_run.pending_gear
    item = state.active_run.pending_gear[0]
    assert item.id not in state.gear
    assert settle_run(state, {}, NOW)["victory"]
    assert state.gear[item.id] == item
    assert state.active_run is None and len(state.gear) == 1
    assert GameState.model_validate_json(state.model_dump_json()).gear[item.id] == item


def test_legacy_boss_snapshot_adds_no_new_rng_or_gear():
    state = make_boss_run(legacy=True)
    before = state.active_run.rng_cursor, state.next_gear_id
    assert conquest.arena(state, PARTY[:3]) is None
    assert state.active_run.last_battle.won
    assert not state.active_run.pending_gear
    assert (state.active_run.rng_cursor, state.next_gear_id) == before


def test_lost_boss_adds_no_gear_or_random_consumption(monkeypatch):
    state = make_boss_run()
    actual = conquest.simulate_battle

    def defeat(*args):
        result = actual(*args)
        result.won = False
        result.reason = "round_limit"
        return result

    monkeypatch.setattr(conquest, "simulate_battle", defeat)
    cursor = state.active_run.rng_cursor
    assert conquest.arena(state, PARTY[:3]) is None
    assert not state.active_run.pending_gear
    assert state.active_run.rng_cursor == cursor


def test_facilities_describe_growth_and_per_region_challenges_without_changing_costs():
    state = GameState()
    before = facility_views(state, load_facilities())
    state.world.unlocked_regions = [1, 2]
    state.world.current_region = 2
    after = facility_views(state, load_facilities())
    assert [view.costs for view in after] == [view.costs for view in before]
    hall = next(item for item in after if item.id == "hall")
    tower = next(item for item in after if item.id == "tower")
    assert "20 级" in hall.description and "境界 6" in hall.description
    assert "纪录独立" in tower.description
    assert state.resources == Resources() and not state.inventory
