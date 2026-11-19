"""问道塔失败结算保留途中真实掉装，不重抽实例或计入失败层。"""

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app.config_loader import load_modes
from app.domain import run_engine
from app.models.equipment import GearItem
from app.models.save import DiscipleState, GameState, Resources

NOW = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
TEMPLATES = {"hero": {
    "name": "测试弟子", "base_stats": {"hp": 100, "atk": 25, "def": 5, "spd": 10},
}}
ENEMIES = {
    "weak": {"id": "weak", "name": "弱敌", "base_stats": {"hp": 1, "atk": 1, "def": 0, "spd": 1}},
    "defeated": {"id": "defeated", "name": "强敌", "base_stats": {"hp": 100000, "atk": 100000, "def": 100000, "spd": 100}},
    "round_limit": {"id": "round_limit", "name": "坚壁", "base_stats": {"hp": 100000, "atk": 1, "def": 100000, "spd": 1}},
}


def start_tower(ending="defeated", *, seed=2, practice=False):
    """隔离两层路线与敌人；掉落沿用正式装备定义和原确定性随机源。"""
    state = GameState(
        equipment_version=1, rng_seed=71, gear_rng_cursor=7, next_gear_id=40,
        resources=Resources(stamina=3), inventory={"ling_cao": 11},
        disciples=[DiscipleState(id="hero", template_id="hero")],
        gear={"owned": GearItem(
            id="owned", definition_id="existing", name="旧佩剑", slot="weapon",
            main_stat="atk", main_value=.05,
        )},
    )
    mode = deepcopy(load_modes()["tower"])
    mode.update(
        node_count=2, boss_every=2, choices_per_step=1, elite_chance=100,
        enemy_growth=0, reward_growth=0, opportunities=False, encounter_variants={},
        encounters={"battle": ["weak"], "elite": ["weak"], "boss": ["weak" if ending == "victory" else ending]},
        kind_stat_multiplier={kind: 1 for kind in ("battle", "elite", "boss")},
        rewards={"battle": {}, "elite": {"cultivation": 20, "spirit_stone": 4, "ling_cao": 4}, "boss": {}},
        defeat_ratio=.5, defeat_floor_reward={"cultivation": 3},
        gear_tier=1, gear_slot="weapon",
    )
    assert run_engine.start_run(
        state, ["hero"], TEMPLATES, mode, NOW, seed=seed, bonds={}, skills={},
        enemies=ENEMIES, affix_pool=[], weapons={}, route_version=2,
    ) is None
    state.active_run.practice = practice
    return state


@pytest.mark.parametrize("ending", ["defeated", "round_limit"])
def test_tower_failure_recovers_same_dropped_gear_after_reload_without_reroll(ending):
    state = start_tower(ending)
    original_gear = deepcopy(state.gear)
    assert run_engine.choose(state, 0) is None
    assert state.active_run.last_battle.won
    assert len(state.active_run.pending_gear) == 1
    pending = deepcopy(state.active_run.pending_gear[0])
    assert pending.id not in state.gear
    assert state.next_gear_id == 41

    # 刷新只恢复待结算实例；第二层真实失败不能重新生成或吞掉第一层装备。
    state = GameState.model_validate_json(state.model_dump_json())
    assert state.active_run.pending_gear == [pending]
    assert run_engine.choose(state, 0) is None
    run = state.active_run
    assert run_engine.run_status(run) == "defeated"
    assert run.last_battle.reason == ending
    assert not run.last_battle.won
    assert run.last_battle.rounds == (20 if ending == "round_limit" else 1)
    assert run.hp > 0 if ending == "round_limit" else run.hp == 0
    before_rng = (run.run_seed, run.rng_cursor, state.rng_seed, state.gear_rng_cursor, state.next_gear_id)

    result = run_engine.settle_run(state, {}, NOW)

    assert result["victory"] is False
    assert result["gear"] == [pending]
    assert state.gear == {**original_gear, pending.id: pending}
    assert (run.run_seed, run.rng_cursor, state.rng_seed, state.gear_rng_cursor, state.next_gear_id) == before_rng
    assert result["loot"] == {"cultivation": 16, "spirit_stone": 2, "ling_cao": 2}
    assert state.inventory["ling_cao"] == 13
    assert state.disciples[0].injury_stacks == 1
    assert not state.disciples[0].busy
    assert state.tower_floor == 1
    assert state.tower_tiers == {"1": 1}
    assert state.world.tower_records["1"] == {"1": 1}
    assert state.active_run is None


def test_tower_failure_without_a_drop_does_not_create_equipment():
    state = start_tower(seed=1)
    original = deepcopy(state.gear)
    assert run_engine.choose(state, 0) is None
    assert state.active_run.last_battle.won
    assert state.active_run.pending_gear == []
    assert run_engine.choose(state, 0) is None
    result = run_engine.settle_run(state, {}, NOW)
    assert result["gear"] == []
    assert state.gear == original
    assert state.next_gear_id == 40


@pytest.mark.parametrize("ending", ["defeated", "victory"])
def test_practice_does_not_generate_or_settle_equipment(ending):
    state = start_tower(ending, practice=True)
    original = deepcopy(state.gear)
    assert run_engine.choose(state, 0) is None
    assert state.active_run.last_battle.won
    assert state.active_run.pending_gear == []
    assert run_engine.choose(state, 0) is None
    result = run_engine.settle_run(state, {}, NOW)
    assert result["gear"] == []
    assert result["loot"] == {}
    assert state.gear == original
    assert state.next_gear_id == 40
    assert state.disciples[0].injury_stacks == 0
    assert state.tower_floor == 0 and state.tower_tiers == {}


def test_practice_settlement_rejects_even_a_restored_real_pending_item():
    state = start_tower()
    original = deepcopy(state.gear)
    assert run_engine.choose(state, 0) is None
    assert len(state.active_run.pending_gear) == 1
    assert run_engine.choose(state, 0) is None
    # 演练奖励门禁同时保护恢复档中已有的待结算实例，不只依赖掉落阶段的禁发。
    state.active_run.practice = True
    state = GameState.model_validate_json(state.model_dump_json())
    result = run_engine.settle_run(state, {}, NOW)
    assert result["gear"] == []
    assert state.gear == original
