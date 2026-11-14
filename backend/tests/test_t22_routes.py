"""固定路线、相邻层段、奖励承诺及历史版本的领域回归。"""

from copy import deepcopy
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.config_loader import load_disciples, load_enemies, load_modes
from app.domain.rng import Pcg32
from app.domain.run_engine import choose, encounter_roster, enemy_units, node_reward, roll_choices, start_run
from app.models.save import DiscipleState, GameState, Resources, RunPartySnapshot


def started(*, version=2, mode=None, enemies=None):
    party = ["guanyu", "zhangfei", "zhaoyun", "zhugeliang", "yuefei", "baisuzhen"]
    state = GameState(resources=Resources(stamina=3), disciples=[
        DiscipleState(id=key, template_id=key, level=10, realm=3) for key in party
    ])
    assert start_run(state, party, load_disciples(), mode or deepcopy(load_modes()["tower"]),
                     datetime(2026, 11, 14, tzinfo=timezone.utc), seed=1,
                     enemies=enemies or deepcopy(load_enemies()), route_version=version) is None
    return state


def test_repeated_early_kind_is_one_honest_route_without_extra_elite():
    mode = deepcopy(load_modes()["tower"])
    mode["elite_chance"] = 0
    run = started(mode=mode).active_run
    assert len(run.choices) == 1
    assert run.choices[0].kind == "battle"
    assert run.choices[0].enemies == mode["encounter_variants"]["battle"][0]
    # 两次类型抽样、一次有效编成抽样，加 PCG 的两次预热。
    assert run.rng_cursor == 5


def test_adjacent_segment_routes_are_distinct_and_never_unlock_future_enemies():
    run = started().active_run
    mode = run.party_snapshot.mode
    for step in range(19):
        for seed in range(12):
            nodes = roll_choices(Pcg32(seed), step, run.party_snapshot)
            assert 1 <= len(nodes) <= 2
            identities = [(node.kind, tuple(node.enemies)) for node in nodes]
            assert len(identities) == len(set(identities))
            for node in nodes:
                variants = mode["encounter_variants"][node.kind]
                current = min(len(variants) - 1, step * len(variants) // mode["node_count"])
                assert node.enemies in variants[max(0, current - 1):current + 1]


def test_only_final_floor_is_boss_and_fixed_boss_does_not_draw_randomness():
    snapshot = started().active_run.party_snapshot
    rng = Pcg32(5)
    cursor = rng.cursor
    nodes = roll_choices(rng, 19, snapshot)
    assert len(nodes) == 1 and nodes[0].kind == "boss"
    assert nodes[0].enemies == encounter_roster(snapshot.mode, "boss", 19)
    assert nodes[0].reward == node_reward("boss", snapshot.mode, 19)
    assert rng.cursor == cursor


def test_new_route_without_variants_still_saves_the_actual_encounter():
    mode = deepcopy(load_modes()["tower"])
    mode.pop("encounter_variants")
    mode["elite_chance"] = 0
    state = started(mode=mode)
    run = state.active_run
    assert len(run.choices) == 1
    assert run.choices[0].enemies == mode["encounters"]["battle"]
    assert choose(state, 0) is None
    assert run.last_battle.loot == node_reward("battle", mode, 0)


@pytest.mark.parametrize("step", range(20))
def test_route_power_matches_actual_enemy_health_rounding(step):
    run = started().active_run
    for node in roll_choices(Pcg32(7), step, run.party_snapshot):
        run.nodes = [node] * (step + 1)
        units = enemy_units(run, node)
        assert node.power == round(sum(unit.attack + .5 * unit.defense + .1 * unit.health for unit in units))


@pytest.mark.parametrize("past_health,current_health,expected_scale", [(10000, 100, 1.3), (100, 10000, .85)])
def test_roster_reward_is_bounded_and_materials_keep_original_amounts(past_health, current_health, expected_scale):
    mode = deepcopy(load_modes()["tower"])
    mode["elite_chance"] = 0
    mode["encounter_variants"]["battle"] = [["past"], ["current"]]
    enemies = deepcopy(load_enemies())
    for key, hp in (("past", past_health), ("current", current_health)):
        enemies[key] = {"id": key, "name": key, "base_stats": {"hp": hp, "atk": 1, "def": 1, "spd": 1}}
    snapshot = started(mode=mode, enemies=enemies).active_run.party_snapshot
    nodes = roll_choices(Pcg32(3), 10, snapshot)
    assert len(nodes) == 2
    past = next(node for node in nodes if node.enemies == ["past"])
    base = node_reward("battle", mode, 10)
    for key, value in base.items():
        assert past.reward[key] == (round(value * expected_scale, 2) if key in {"cultivation", "spirit_stone", "reputation"} else value)


def test_entering_route_uses_saved_roster_power_and_reward():
    state = started()
    run = state.active_run
    node = run.choices[0]
    promised = node.model_copy(deep=True)
    # 将已保存收益设为与通用层奖励不同，确保进入时不会重新计算覆盖承诺。
    node.reward = {"cultivation": 12.34, "han_tie": 2}
    assert choose(state, 0) is None
    battle = run.last_battle
    assert battle.won
    assert [unit.template_id for unit in battle.initial_units if unit.side == "enemy"] == promised.enemies
    assert battle.enemy_power == promised.power
    assert battle.loot == run.pending_loot == {"cultivation": 12.34, "han_tie": 2}


def test_legacy_snapshot_keeps_original_rng_and_empty_rosters():
    state = started(version=1)
    run = state.active_run
    assert run.rng_cursor == 4
    assert len(run.choices) == 2
    assert all(node.kind == "battle" and node.enemies == [] for node in run.choices)
    data = state.model_dump(mode="json")
    del data["active_run"]["party_snapshot"]["route_version"]
    for node in data["active_run"]["choices"]:
        del node["enemies"]
    restored = GameState.model_validate(data)
    assert restored.active_run.party_snapshot.route_version == 1
    assert choose(state, 0) is None
    assert choose(restored, 0) is None
    assert state.active_run == restored.active_run
    with pytest.raises(ValidationError):
        RunPartySnapshot(combatants=(), route_version=3)


@pytest.mark.parametrize("step", [0, 10, 19])
def test_legacy_empty_roster_keeps_pre_t22_saved_floor_bands(step):
    mode = deepcopy(load_modes()["tower"])
    mode["elite_chance"] = 0
    mode["encounters"]["battle"] = ["stone_guard"]
    mode["encounter_variants"]["battle"] = [["cloud_archer"], ["jade_warden"]]
    run = started(version=1, mode=mode).active_run
    assert run.choices[0].enemies == []
    # 进入战斗前节点已追加；旧局按保存的层段变体还原，不能退回固定 encounters。
    run.nodes = [run.choices[0]] * (step + 1)
    expected = ["cloud_archer"] if step < 10 else ["jade_warden"]
    assert [unit.template_id for unit in enemy_units(run, run.choices[0])] == expected
