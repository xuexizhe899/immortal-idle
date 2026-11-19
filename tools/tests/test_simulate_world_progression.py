"""真实规则模拟的预算、成长重试与配置隔离。"""

from pathlib import Path
import sys
from datetime import timedelta

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulate_world_progression import (  # noqa: E402
    Pcg32, ROSTER, Simulation, conquest, equipment, load_modes, load_sects, load_world, recruit,
)


def ready_party():
    simulation = Simulation(7, "map_30m", "formal")
    simulation.state.resources.reputation = 1000
    simulation.budget = 3600
    for identity in ROSTER:
        assert recruit.recruit(simulation.state, identity, simulation.templates) is None
    simulation.state.world.pending_invasions["1"] = 0
    simulation.state.world.unlocked_areas["1"] = 3
    simulation.attempted_this_session = {f"r1:{kind}:{area}" for area in range(1, 4) for kind in ("gate", "invasion")}
    return simulation


def fill_equipment(simulation):
    rng = Pcg32(123)
    for disciple in simulation.state.disciples:
        for slot in equipment.SLOTS:
            item = equipment.grant_drop(simulation.state, rng, 1, slot, config=simulation.gear_rules)
            assert equipment.equip_gear(simulation.state, item.id, disciple.id) is None


def test_parameter_profile_does_not_mutate_cached_live_configuration():
    baseline_cost = load_modes()["tower"]["stamina_cost"]
    baseline_scale = load_world()["regions"][0]["areas"][2].get("invasion_multiplier", 1.3)
    simulation = Simulation(7, "tower_60m", "formal")
    assert simulation.modes["tower"]["stamina_cost"] == baseline_cost
    assert simulation.world["regions"][0]["areas"][2]["invasion_multiplier"] == baseline_scale
    simulation.modes["tower"]["stamina_cost"] = 9
    simulation.world["regions"][0]["areas"][2]["invasion_multiplier"] = 9
    assert load_modes()["tower"]["stamina_cost"] == baseline_cost
    assert load_world()["regions"][0]["areas"][2].get("invasion_multiplier", 1.3) == baseline_scale


def test_tower_policy_never_starts_with_less_than_profile_stamina_cost():
    simulation = Simulation(7, "tower_60m", "formal")
    simulation.state.resources.stamina = load_modes()["tower"]["stamina_cost"] - 1
    simulation.state.world.pending_invasions["1"] = 0
    simulation.attempted_this_session = {f"r1:{kind}:{area}" for area in range(1, 4) for kind in ("gate", "invasion")}
    assert simulation.target()[0] != "legacy_tower"


def test_failed_sects_cannot_consume_the_last_dungeon_budget():
    simulation = ready_party()
    simulation.state.facility_levels["hall"] = 3
    conquest.ensure_sects(simulation.state, load_sects(), simulation.enemies, simulation.world)
    for sect in simulation.state.sects[:6]:
        sect.conquered = True
    simulation.state.resources.stamina = 6
    for _ in range(2):
        identity, sect = simulation.target()
        assert identity == "sect"
        simulation.play_run(identity, sect)
        assert not simulation.runs[-1]["victory"]
    identity, sect = simulation.target()
    assert identity.startswith("r1:dungeon:") and sect is None
    assert simulation.state.resources.stamina >= 2


def test_unchanged_failed_input_is_not_retried_after_a_new_login():
    simulation = ready_party()
    before = simulation.party_fingerprint()
    simulation.play_run("r1:gate:3", None)
    assert not simulation.runs[-1]["victory"]
    assert before in simulation.failed_inputs["r1:gate:3"]
    simulation.tick(target=simulation.now + timedelta(hours=12))
    simulation.attempted_this_session.clear()
    assert simulation.party_fingerprint() == before
    assert not simulation.eligible("r1:gate:3")


@pytest.mark.parametrize("stat", ["damage", "healing", "shielding"])
def test_non_power_equipment_growth_allows_a_real_retry(stat):
    simulation = ready_party()
    disciple = simulation.state.disciples[0]
    item = equipment.grant_drop(simulation.state, Pcg32(123), 1, "ring", config=simulation.gear_rules)
    item.affix, item.affix_value = stat, .02
    assert equipment.equip_gear(simulation.state, item.id, disciple.id) is None
    simulation.failed_inputs["r1:gate:3"] = {simulation.party_fingerprint()}
    simulation.attempted_this_session.clear()
    previous_score = simulation.score()
    assert not simulation.eligible("r1:gate:3")
    item.affix_value = .03
    assert simulation.score() == previous_score
    assert simulation.eligible("r1:gate:3")


def test_full_equipment_prefers_the_highest_available_dungeon_then_falls_back():
    simulation = ready_party()
    fill_equipment(simulation)
    assert simulation.dungeon_target().area == 3
    for index in (1, 2):
        simulation.failed_inputs[f"r1:dungeon:3:{index}"] = {simulation.party_fingerprint()}
    assert simulation.dungeon_target().area == 2


@pytest.mark.parametrize("slot, area", [("boots", 1), ("ring", 2)])
def test_missing_equipment_prefers_its_targeted_dungeon(slot, area):
    simulation = ready_party()
    fill_equipment(simulation)
    simulation.state.disciples[-1].gear_slots.pop(slot)
    target = simulation.dungeon_target()
    assert target.gear_slot == slot and target.area == area
