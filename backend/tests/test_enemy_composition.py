"""敌人层段编成、精英/首领系数与常驻被动。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from app.config_loader import load_disciples, load_enemies, load_modes
from app.domain.run_engine import encounter_roster, enemy_power, enemy_units, start_run
from app.models.save import DiscipleState, GameState, Resources, RunNode

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)

TEMPLATES = {
    "hero": {
        "id": "hero", "name": "测试弟子", "lean": "attack", "rarity": 1,
        "base_stats": {"hp": 100, "atk": 10, "def": 5, "spd": 10},
    },
}
ENEMIES = {
    "dummy": {
        "id": "dummy", "name": "木桩", "base_stats": {"hp": 100, "atk": 10, "def": 10, "spd": 8},
        "passive": {
            "id": "dummy-passive", "name": "木甲", "type": "passive",
            "effects": [], "condition": "always", "bonuses": {"def": .2, "hp": .5},
        },
    },
}


def base_mode(**overrides) -> dict:
    """构造可启动出征的最小模式。"""
    mode = {
        "id": "test", "name": "测试塔", "enabled": True, "stamina_cost": 1,
        "node_count": 20, "start_hp": 1000, "base_enemy_power": 20,
        "enemy_growth": 0.0, "reward_growth": 0.1, "damage_scale": 60,
        "boss_every": 20, "choices_per_step": 2, "elite_chance": 20,
        "defeat_ratio": 0.5, "defeat_floor_reward": {"cultivation": 1},
        "rewards": {
            "battle": {"cultivation": 1}, "elite": {"cultivation": 2},
            "boss": {"cultivation": 3},
        },
        "encounters": {"battle": ["dummy"], "elite": ["dummy"], "boss": ["dummy"]},
    }
    mode.update(overrides)
    return mode


def start(mode: dict) -> GameState:
    state = GameState(
        resources=Resources(stamina=3),
        disciples=[DiscipleState(id="hero", template_id="hero")],
    )
    assert start_run(
        state, ["hero"], TEMPLATES, mode, NOW, seed=1,
        enemies=ENEMIES, affix_pool=[], skills={}, bonds={},
    ) is None
    return state


def test_encounter_roster_uses_five_segments_and_falls_back() -> None:
    """20 层均分为五段；旧模式没有 variants 时使用固定编成。"""
    mode = {
        "node_count": 20,
        "encounters": {"battle": ["fallback"]},
        "encounter_variants": {"battle": [["a"], ["b"], ["c"], ["d"], ["e"]]},
    }
    assert [
        encounter_roster(mode, "battle", step)[0]
        for step in (0, 3, 4, 7, 8, 11, 12, 15, 16, 19)
    ] == ["a", "a", "b", "b", "c", "c", "d", "d", "e", "e"]
    assert encounter_roster(
        {"node_count": 20, "encounters": {"battle": ["fallback"]}}, "battle", 5,
    ) == ["fallback"]


def test_elite_and_boss_multipliers_and_always_passive_are_frozen() -> None:
    """精英/首领系数与常驻被动属性在创建敌人时生效。"""
    state = start(base_mode(kind_stat_multiplier={"battle": 1.0, "elite": 1.5, "boss": 2.0}))
    run = state.active_run

    run.nodes = [RunNode(kind="battle", enemy="battle_0", power=0)]
    battle = enemy_units(run, RunNode(kind="battle", enemy="battle_0", power=0))[0]
    assert battle.defense == 12  # 10 × 1.2
    assert battle.health == 150  # 100 × 1.5
    assert battle.speed == 8

    run.nodes = [RunNode(kind="elite", enemy="elite_0", power=0)]
    elite = enemy_units(run, RunNode(kind="elite", enemy="elite_0", power=0))[0]
    assert elite.defense == 18
    assert elite.health == 225

    run.nodes = [RunNode(kind="boss", enemy="boss_0", power=0)] * 20
    boss = enemy_units(run, RunNode(kind="boss", enemy="boss_0", power=0))[0]
    assert boss.defense == 24
    assert boss.health == 300


def test_enemy_power_reports_kind_multiplier() -> None:
    """节点展示战力与实际精英/首领系数一致。"""
    mode = {
        "base_enemy_power": 20, "enemy_growth": 0,
        "kind_stat_multiplier": {"battle": 1.0, "elite": 1.5, "boss": 2.0},
    }
    assert enemy_power(0, mode, "battle") == 20
    assert enemy_power(0, mode, "elite") == 30
    assert enemy_power(0, mode, "boss") == 40


def test_tower_config_uses_all_ten_enemies_and_five_segments() -> None:
    """20 层编成覆盖十种敌人，首领层包含问道真灵。"""
    mode = load_modes()["tower"]
    variants = mode["encounter_variants"]
    used = {
        enemy_id for rosters in variants.values()
        for roster in rosters for enemy_id in roster
    }
    assert used == set(load_enemies())
    assert len(variants["battle"]) == 5
    assert len(variants["elite"]) == 5
    assert len(variants["boss"]) == 1
    assert "tower_master" in variants["boss"][0]
    assert set(mode["kind_stat_multiplier"]) == {"battle", "elite", "boss"}


def test_tower_start_snapshot_keeps_encounter_variants() -> None:
    """出发快照固化编成；修改配置不改变本局。"""
    mode = deepcopy(load_modes()["tower"])
    state = GameState(
        resources=Resources(stamina=3),
        disciples=[DiscipleState(id="hero", template_id="guanyu")],
    )
    assert start_run(
        state, ["hero"], load_disciples(), mode, NOW, seed=1,
        bonds={}, skills={}, enemies=load_enemies(), affix_pool=[],
    ) is None
    frozen = state.active_run.party_snapshot
    mode["encounter_variants"]["battle"][0] = ["stone_guard"]
    assert frozen.mode["encounter_variants"]["battle"][0] != ["stone_guard"]
