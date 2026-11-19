"""地区进度、时钟、快照与令牌使用的隔离状态回归。"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from app.config_loader import load_enemies, load_modes, load_world
from app.domain.world import (
    ascend, ensure_world, finish_world_node, prepare_world_node, tower_mode, travel_region, world_view,
)
from app.models.save import ActiveRun, DiscipleState, GameState, Resources

NOW = datetime(2026, 11, 19, tzinfo=timezone.utc)


@pytest.fixture
def config():
    return deepcopy(load_world())


def make_state(config):
    state = GameState(rng_seed=71)
    ensure_world(state, NOW, config)
    return state


def prepare(state, identity, config, practice=False):
    node, error = prepare_world_node(state, identity, config, practice)
    assert error is None
    return node


def win(state, identity, config, now=NOW):
    node = prepare(state, identity, config)
    return finish_world_node(state, node, True, now, config)


def clear_region(state, region, config):
    for area in range(1, 4):
        win(state, f"r{region}:gate:{area}", config)
        for key, value in win(state, f"r{region}:invasion:{area}", config).items():
            if key == config["ascension_token"]:
                state.inventory[key] = state.inventory.get(key, 0) + int(value)


def test_two_complete_maps_have_stable_targets_and_real_enemy_references(config):
    state = make_state(config)
    before = state.model_dump_json()
    view = world_view(state, config)
    assert state.model_dump_json() == before
    assert len(view.regions) == 2
    assert view == world_view(state, config)
    enemies = load_enemies()
    for region in view.regions:
        assert len(region.areas) == 3
        assert len({node.id for node in region.nodes}) == len(region.nodes)
        assert sum(node.kind == "sect" for node in region.nodes) == 9
        assert sum(node.kind == "dungeon" for node in region.nodes) == 6
        assert sum(node.kind == "gate" for node in region.nodes) == 3
        assert sum(node.kind == "invasion" for node in region.nodes) == 3
        assert {node.gear_slot for node in region.nodes if node.kind == "dungeon"} >= {"weapon", "armor", "boots", "ring"}
        assert all(enemy in enemies for node in region.nodes for enemy in node.enemy_ids)
        assert all(0 <= node.x <= 100 and 0 <= node.y <= 100 for node in region.nodes)


def test_locked_region_and_area_cannot_be_entered_even_in_practice(config):
    state = make_state(config)
    before = state.model_dump_json()
    assert prepare_world_node(state, "r2:dungeon:1:1", config)[1] == "目标不在当前地区"
    assert "守关" in prepare_world_node(state, "r1:dungeon:2:1", config, True)[1]
    assert "守关" in prepare_world_node(state, "r1:invasion:1", config)[1]
    assert state.model_dump_json() == before


def test_gate_first_victory_opens_next_area_and_rewards_only_once(config):
    state = make_state(config)
    gate = prepare(state, "r1:gate:1", config)
    before_resources = state.resources.model_dump()
    rewards = finish_world_node(state, gate, True, NOW, config)
    assert rewards == config["regions"][0]["areas"][0]["first_reward"]
    assert state.resources.model_dump() == before_resources
    assert state.world.unlocked_areas["1"] == 2
    assert prepare_world_node(state, "r1:dungeon:2:1", config)[1] is None
    assert finish_world_node(state, gate, True, NOW, config) == {}
    assert win(state, "r1:gate:1", config) == {}
    win(state, "r1:gate:2", config)
    win(state, "r1:gate:3", config)
    assert state.world.unlocked_areas["1"] == 3


def test_failure_and_practice_never_change_formal_progress(config):
    state = make_state(config)
    gate = prepare(state, "r1:gate:1", config)
    before = state.model_dump_json()
    assert finish_world_node(state, gate, False, NOW, config) == {}
    assert finish_world_node(state, gate, True, NOW, config, practice=True) == {}
    assert state.model_dump_json() == before
    practice = prepare(state, "r1:gate:1", config, True)
    assert practice["completion_rewards"] == {}
    assert practice["mode_overrides"]["stamina_cost"] == 0
    assert all(not value for value in practice["mode_overrides"]["rewards"].values())
    assert finish_world_node(state, practice, True, NOW, config) == {}
    assert state.model_dump_json() == before


def test_key_invasions_follow_area_gates_and_previous_key_invasion(config):
    state = make_state(config)
    win(state, "r1:gate:1", config)
    win(state, "r1:gate:2", config)
    assert "前一片区" in prepare_world_node(state, "r1:invasion:2", config)[1]
    win(state, "r1:invasion:1", config)
    assert prepare_world_node(state, "r1:invasion:2", config)[1] is None


def test_completion_uses_snapshot_rewards_and_unlock_not_new_config(config):
    state = make_state(config)
    gate = prepare(state, "r1:gate:1", config)
    frozen = deepcopy(gate)
    config["regions"][0]["areas"][0]["first_reward"] = {"spirit_stone": 999999}
    config["regions"][0]["areas"][0]["boss"] = ["tower_master"]
    assert gate == frozen
    assert finish_world_node(state, gate, True, NOW, config) == frozen["completion_rewards"]
    assert state.world.unlocked_areas["1"] == 2


def test_enemy_intelligence_initialization_regeneration_and_cap(config):
    state = make_state(config)
    assert state.world.pending_invasions["1"] == 1
    assert not ensure_world(state, NOW, config)
    assert not ensure_world(state, NOW + timedelta(hours=3), config)
    assert ensure_world(state, NOW + timedelta(hours=4), config)
    assert state.world.pending_invasions["1"] == 2
    assert world_view(state, config).invasions.next_at == NOW + timedelta(hours=8)
    ensure_world(state, NOW + timedelta(hours=25), config)
    assert state.world.pending_invasions["1"] == 3
    assert world_view(state, config).invasions.next_at is None
    assert state.world.last_invasion_at["1"] == NOW + timedelta(hours=25)
    assert not ensure_world(state, NOW + timedelta(hours=26), config)


def test_time_rollback_cannot_advance_intelligence_or_move_anchor_backwards(config):
    state = make_state(config)
    ensure_world(state, NOW + timedelta(hours=4), config)
    before = state.model_dump_json()
    assert not ensure_world(state, NOW - timedelta(hours=7), config)
    assert state.model_dump_json() == before
    ensure_world(state, NOW + timedelta(hours=7), config)
    assert state.world.pending_invasions["1"] == 2
    assert state.world.last_invasion_at["1"] == NOW + timedelta(hours=4)


def test_raid_is_zero_stamina_failure_retains_wave_and_claims_once(config):
    state = make_state(config)
    state.resources.stamina = 0
    raid = prepare(state, "r1:raid", config)
    assert raid["mode_overrides"]["stamina_cost"] == 0
    assert all(not value for value in raid["mode_overrides"]["rewards"].values())
    before = state.model_dump_json()
    assert finish_world_node(state, raid, False, NOW, config) == {}
    assert state.model_dump_json() == before
    rewards = finish_world_node(state, raid, True, NOW, config)
    assert rewards == config["invasion"]["reward"]
    assert state.world.pending_invasions["1"] == 0
    assert state.world.invasion_waves["1"] == 2
    assert finish_world_node(state, raid, True, NOW, config) == {}
    assert prepare_world_node(state, "r1:raid", config)[1]
    ensure_world(state, NOW + timedelta(hours=4), config)
    second = prepare(state, "r1:raid", config)
    assert second["enemy_scale"] > raid["enemy_scale"]
    assert second["claim_key"] != raid["claim_key"]


def test_raid_difficulty_is_capped_and_completion_uses_frozen_capacity(config):
    state = make_state(config)
    state.world.invasion_waves["1"] = 10000
    state.world.pending_invasions["1"] = 3
    raid = prepare(state, "r1:raid", config)
    assert raid["enemy_scale"] == config["invasion"]["wave_scale_cap"]
    assert raid["enemy_scale"] < config["regions"][1]["enemy_scale"]
    config["invasion"]["pending_cap"] = 9
    finish_world_node(state, raid, True, NOW + timedelta(hours=2), config)
    assert state.world.last_invasion_at["1"] == NOW + timedelta(hours=2)


def test_only_dungeons_override_the_existing_tower_defeat_policy(config):
    state = make_state(config)
    tower = prepare(state, "r1:tower", config)
    dungeon = prepare(state, "r1:dungeon:1:1", config)
    assert "defeat_ratio" not in tower["mode_overrides"]
    assert "defeat_floor_reward" not in tower["mode_overrides"]
    assert dungeon["mode_overrides"]["defeat_ratio"] == 1
    assert dungeon["mode_overrides"]["defeat_floor_reward"] == {}


def test_both_tower_entry_paths_preserve_same_complete_rules_and_current_cost(config):
    state = make_state(config)
    state.world.current_region = 2
    state.world.unlocked_regions = [1, 2]
    config["tower_stamina_cost"] = 2
    base = deepcopy(load_modes()["tower"])
    original = deepcopy(base)
    legacy = tower_mode(state, base, config)
    mapped = tower_mode(state, base, config)
    node = prepare(state, "r2:tower", config)
    mapped.update(node["mode_overrides"])
    assert mapped == legacy
    assert mapped["stamina_cost"] == node["stamina_cost"] == 2
    assert mapped["encounters"] == base["encounters"]
    assert mapped["encounter_variants"] == base["encounter_variants"]
    assert mapped["enemy_growth"] == base["enemy_growth"]
    assert mapped["defeat_ratio"] == base["defeat_ratio"]
    assert mapped["rewards"]["battle"]["cultivation"] == base["rewards"]["battle"]["cultivation"] * 2.5
    assert base == original


def test_dungeons_supply_personal_breakthrough_reputation_and_freeze_it(config):
    state = make_state(config)
    first = prepare(state, "r1:dungeon:1:1", config)
    assert first["mode_overrides"]["rewards"]["battle"]["reputation"] == 2
    assert first["mode_overrides"]["rewards"]["elite"]["reputation"] == 3
    assert first["mode_overrides"]["rewards"]["boss"]["reputation"] == 5
    state.world.unlocked_areas["1"] = 2
    later = prepare(state, "r1:dungeon:2:1", config)
    assert later["mode_overrides"]["rewards"]["battle"]["reputation"] == 2.7
    config["dungeon_reputation"] = 20
    assert first["mode_overrides"]["rewards"]["battle"]["reputation"] == 2
    assert later["mode_overrides"]["rewards"]["battle"]["reputation"] == 2.7


def test_empty_raid_still_allows_practice_without_growth(config):
    state = make_state(config)
    state.world.pending_invasions["1"] = 0
    before = state.model_dump_json()
    for _ in range(3):
        raid = prepare(state, "r1:raid", config, True)
        assert finish_world_node(state, raid, True, NOW, config) == {}
    assert state.model_dump_json() == before


def test_full_capacity_does_not_bank_extra_waves_after_success(config):
    state = make_state(config)
    ensure_world(state, NOW + timedelta(hours=20), config)
    raid = prepare(state, "r1:raid", config)
    finish_world_node(state, raid, True, NOW + timedelta(hours=23), config)
    ensure_world(state, NOW + timedelta(hours=26), config)
    assert state.world.pending_invasions["1"] == 2
    ensure_world(state, NOW + timedelta(hours=27), config)
    assert state.world.pending_invasions["1"] == 3


def test_ascension_requires_final_invasion_and_spends_one_token_only(config):
    state = make_state(config)
    state.inventory[config["ascension_token"]] = 2
    assert "最终" in ascend(state, NOW, config)
    assert "尚未开放" in travel_region(state, 2, NOW, config)
    clear_region(state, 1, config)
    held = state.inventory[config["ascension_token"]]
    assert world_view(state, config).ascension.can_ascend
    assert ascend(state, NOW, config) is None
    assert state.world.current_region == 2
    assert state.world.unlocked_regions == [1, 2]
    assert state.inventory[config["ascension_token"]] == held - 1
    assert ascend(state, NOW, config)
    assert travel_region(state, 1, NOW, config) is None
    assert "已开放" in ascend(state, NOW, config)
    assert state.inventory[config["ascension_token"]] == held - 1


def test_ascension_without_token_or_with_active_run_is_rejected(config):
    state = make_state(config)
    clear_region(state, 1, config)
    state.inventory[config["ascension_token"]] = 0
    assert "升仙令" in ascend(state, NOW, config)
    state.inventory[config["ascension_token"]] = 1
    state.active_run = ActiveRun(run_seed=12, started_at=NOW)
    before = state.model_dump_json()
    assert "结算" in ascend(state, NOW, config)
    assert "结算" in travel_region(state, 1, NOW, config)
    assert "结算" in prepare_world_node(state, "r1:gate:1", config)[1]
    assert state.model_dump_json() == before


def test_region_travel_retains_growth_and_tower_history_with_independent_clocks(config):
    state = make_state(config)
    state.disciples = [DiscipleState(id="hero", template_id="guanyu", level=9)]
    state.resources = Resources(cultivation=1000, spirit_stone=100, stamina=6)
    state.inventory["han_tie"] = 17
    state.tower_floor = 20
    state.tower_tiers = {"1": 20, "2": 7}
    clear_region(state, 1, config)
    growth = deepcopy((state.disciples, state.resources, state.inventory["han_tie"]))
    assert ascend(state, NOW + timedelta(hours=1), config) is None
    assert state.tower_tiers == {} and state.tower_floor == 20
    assert state.world.last_invasion_at["2"] == NOW + timedelta(hours=1)
    state.tower_tiers = {"1": 3}
    assert travel_region(state, 1, NOW + timedelta(hours=4), config) is None
    assert state.tower_tiers == {"1": 20, "2": 7}
    assert state.world.pending_invasions == {"1": 2, "2": 1}
    assert travel_region(state, 2, NOW + timedelta(hours=5), config) is None
    assert state.tower_tiers == {"1": 3}
    assert state.world.pending_invasions["2"] == 2
    assert (state.disciples, state.resources, state.inventory["han_tie"]) == growth
    assert "r1:invasion:3" in state.world.cleared_nodes


def test_second_region_has_playable_harder_content_and_a_complete_final_milestone(config):
    state = make_state(config)
    first = prepare(state, "r1:dungeon:1:1", config)
    clear_region(state, 1, config)
    assert ascend(state, NOW, config) is None
    second = prepare(state, "r2:dungeon:1:1", config)
    assert second["enemy_scale"] > first["enemy_scale"]
    assert second["gear_tier"] == 2
    clear_region(state, 2, config)
    final = world_view(state, config).ascension
    assert final.target_region is None and not final.can_ascend
    assert "尚未开放" in final.reason
    restored = GameState.model_validate_json(state.model_dump_json())
    assert restored == state
