"""地区、出征、个人装备与挂机结算在真实命令边界上的集成回归。"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import update

from app.api import state as state_api
from app.config_loader import load_equipment, load_modes, load_world
from app.db import create_engine, create_session_factory
from app.domain import run_engine
from app.domain.duty import personal_duty_rates, rates_of, record_event
from app.domain.equipment import combat_equipment_bonuses, equip_gear, upgrade_gear
from app.domain.training import preview
from app.domain.world import prepare_world_node, travel_region
from app.main import app
from app.models.equipment import GearItem
from app.models.save import DiscipleState, DutySlot, GameState, Resources
from app.repositories.saves import SaveRepository
from app.repositories.tables import metadata, save_slots

NOW = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
MATERIAL = "lian_qi_jing_cui"
TEMPLATES = {"test": {
    "name": "测试弟子", "lean": "attack", "rarity": 1,
    "base_stats": {"hp": 100, "atk": 25, "def": 5, "spd": 10},
}}
ENEMIES = {
    "weak": {"id": "weak", "name": "弱敌", "base_stats": {"hp": 1, "atk": 1, "def": 0, "spd": 1}},
    "strong": {"id": "strong", "name": "强敌", "base_stats": {"hp": 100000, "atk": 100000, "def": 100000, "spd": 100}},
}


def start_staged_run(state=None, *, mode_id="dungeon", world_node_id="r1:dungeon:1:1"):
    """用正常战斗先胜精英再败首领，固定种子保证首战实际掉装。"""
    state = state or GameState(
        equipment_version=1, rng_seed=71, resources=Resources(stamina=3),
        disciples=[DiscipleState(id="hero", template_id="test")],
    )
    node = None
    if world_node_id:
        node, error = prepare_world_node(state, world_node_id, load_world())
        assert error is None
    mode = deepcopy(load_modes()["tower"])
    if node:
        mode.update(node["mode_overrides"])
        mode["world_node"] = node
    mode.update(
        id=mode_id, gear_tier=1, gear_slot="weapon",
        node_count=2, boss_every=2, choices_per_step=1, elite_chance=100,
        enemy_growth=0, opportunities=False, encounter_variants={},
        encounters={"battle": ["weak"], "elite": ["weak"], "boss": ["strong"]},
        kind_stat_multiplier={"battle": 1, "elite": 1, "boss": 1},
        rewards={"battle": {}, "elite": {"cultivation": 20, "spirit_stone": 4, MATERIAL: 3}, "boss": {}},
    )
    assert run_engine.start_run(
        state, [d.id for d in state.disciples], TEMPLATES, mode, NOW,
        seed=2, bonds={}, skills={}, enemies=ENEMIES, affix_pool=[], weapons={}, route_version=2,
    ) is None
    state.active_run.world_node_id = node["id"] if node else ""
    return state


def real_state(strong=True):
    bonuses = {key: 100 for key in ("hp", "atk", "def", "spd")} if strong else {}
    return GameState(
        equipment_version=1, rng_seed=71, resources=Resources(stamina=0),
        disciples=[DiscipleState(id="hero", template_id="guanyu", bonuses=bonuses)],
    )


@pytest_asyncio.fixture
async def world_client(tmp_path, monkeypatch):
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW if tz else NOW.replace(tzinfo=None)

    monkeypatch.setattr(state_api, "datetime", FrozenDateTime)
    monkeypatch.setattr("app.api.world.secrets.randbits", lambda bits: 2)
    engine = create_engine(f"sqlite+aiosqlite:///{(tmp_path / 'world-runs.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    factory = create_session_factory(engine)
    app.state.session_factory = factory

    async def create_slot(state, settled_at=NOW):
        state_api.initialize_world(state, NOW)
        async with factory() as session:
            slot = await SaveRepository(session).create_slot("地区出征验证", state)
            await session.execute(update(save_slots).where(save_slots.c.slot_id == slot).values(
                last_settled_at=settled_at.isoformat(),
            ))
            await session.commit()
        return slot

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, factory, create_slot
    await engine.dispose()


async def saved(factory, slot):
    async with factory() as session:
        state, revision = await SaveRepository(session).get_state(slot)
        return state.model_dump(mode="json"), revision


async def finish_run(client, slot, content):
    for _ in range(60):
        if content["status"] in {"cleared", "defeated"}:
            return content
        affix = content["status"] == "choosing_affix"
        command = {"affix_id": content["run"]["affix_options"][0]} if affix else {"choice": 0}
        response = await client.post(f"/api/saves/{slot}/run/{'affix' if affix else 'choose'}", json={
            "revision": content["revision"], **command,
        })
        assert response.status_code == 200, response.text
        content = response.json()
    pytest.fail("本次固定快照未在预期节点数内结束")


async def test_world_browsing_is_read_only_and_locked_travel_is_atomic(world_client):
    client, factory, create_slot = world_client
    slot = await create_slot(real_state())
    before = await saved(factory, slot)
    first = await client.get(f"/api/saves/{slot}/world")
    second = await client.get(f"/api/saves/{slot}/world")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert await saved(factory, slot) == before
    denied = await client.post(f"/api/saves/{slot}/world/travel", json={
        "revision": before[1], "region_id": 2,
    })
    assert denied.status_code == 400
    assert await saved(factory, slot) == before


async def test_official_raid_is_playable_at_zero_stamina_and_claimed_once(world_client):
    client, factory, create_slot = world_client
    slot = await create_slot(real_state())
    original, revision = await saved(factory, slot)
    assert original["resources"]["stamina"] == 0
    command = {"revision": revision, "node_id": "r1:raid", "party": ["hero"]}
    started = await client.post(f"/api/saves/{slot}/world/start", json=command)
    assert started.status_code == 200, started.text
    assert started.json()["state"]["resources"]["stamina"] == 0
    assert (await client.post(f"/api/saves/{slot}/world/start", json=command)).status_code == 409
    ended = await finish_run(client, slot, started.json())
    assert ended["status"] == "cleared"
    settle_command = {"revision": ended["revision"]}
    response = await client.post(f"/api/saves/{slot}/run/settle", json=settle_command)
    assert response.status_code == 200
    content = response.json()
    assert content["loot"] == load_world()["invasion"]["reward"]
    assert content["gear"] == []
    assert content["state"]["world"]["pending_invasions"]["1"] == 0
    assert content["state"]["world"]["invasion_waves"]["1"] == 2
    assert content["state"]["resources"]["stamina"] == 0
    assert (await client.post(f"/api/saves/{slot}/run/settle", json=settle_command)).status_code == 409
    after = await saved(factory, slot)
    assert (await client.post(f"/api/saves/{slot}/run/settle", json={"revision": after[1]})).status_code == 400
    assert await saved(factory, slot) == after


@pytest.mark.parametrize("region_id", [1, 2])
async def test_map_and_legacy_tower_share_cost_rewards_and_frozen_battle_inputs(world_client, monkeypatch, region_id):
    client, _, create_slot = world_client
    config = deepcopy(load_world())
    config["tower_stamina_cost"] = 2
    config["regions"][region_id - 1]["gear_tier"] = region_id + 2
    monkeypatch.setattr("app.api.run.load_world", lambda: config)
    monkeypatch.setattr("app.api.world.load_world", lambda: config)
    state = real_state()
    state.resources.stamina = 10
    state.world.unlocked_regions = list(range(1, region_id + 1))
    state.world.current_region = region_id
    slots = [await create_slot(state.model_copy(deep=True)) for _ in range(2)]
    responses = []
    for slot, path in zip(slots, ("run/start", "world/start")):
        initial = (await client.get(f"/api/saves/{slot}/world")).json()
        command = {"revision": initial["revision"], "party": ["hero"]}
        command.update({"mode": "tower"} if path == "run/start" else {"node_id": f"r{region_id}:tower"})
        response = await client.post(f"/api/saves/{slot}/{path}", json=command)
        assert response.status_code == 200, response.text
        responses.append(response.json())
    first, second = responses
    assert first["state"]["resources"]["stamina"] == second["state"]["resources"]["stamina"] == 8
    legacy, atlas = first["run"]["party_snapshot"], second["run"]["party_snapshot"]
    assert legacy["combatants"] == atlas["combatants"]
    assert first["run"]["choices"] == second["run"]["choices"]
    assert legacy["mode"]["gear_tier"] == atlas["mode"]["gear_tier"] == region_id + 2
    for key in ("stamina_cost", "rewards", "defeat_ratio", "defeat_floor_reward", "encounters", "encounter_variants", "enemy_growth", "node_count", "boss_every", "kind_stat_multiplier"):
        assert legacy["mode"][key] == atlas["mode"][key], key


async def test_map_previews_match_actual_region_tower_and_retrial_rewards(world_client):
    from app.config_loader import load_sects
    from app.domain.world import tower_mode

    client, _, create_slot = world_client
    state = real_state()
    state.facility_levels["hall"] = 3
    state.world.unlocked_regions = [1, 2]
    state.world.unlocked_areas = {"1": 3, "2": 3}
    slot = await create_slot(state)
    response = await client.get(f"/api/saves/{slot}/world")
    assert response.status_code == 200, response.text
    config = load_world()
    styles = {style["name"]: style for style in load_sects()["styles"]}
    for region in response.json()["world"]["regions"]:
        state.world.current_region = region["id"]
        assert region["tower_rewards"] == tower_mode(state, load_modes()["tower"], config)["rewards"]
        for node in region["nodes"]:
            if node["kind"] != "sect":
                continue
            sect = next(sect for sect in state.sects if sect.id == node["sect_id"])
            scale = next(item["reward_scale"] for item in config["regions"] if item["id"] == region["id"])
            assert node["retrial_rewards"] == {
                key: value * scale for key, value in styles[sect.style]["retrial_reward"].items()
            }


@pytest.mark.parametrize("strong", [False, True])
@pytest.mark.parametrize("node_id", ["r1:raid", "r1:gate:1", "r1:invasion:3"])
async def test_practice_has_no_rewards_new_injuries_or_official_progress(world_client, strong, node_id):
    client, factory, create_slot = world_client
    state = real_state(strong)
    state.world.pending_invasions["1"] = 0
    if node_id == "r1:invasion:3":
        state.world.unlocked_areas["1"] = 3
        state.world.cleared_nodes = ["r1:gate:1", "r1:gate:2", "r1:gate:3", "r1:invasion:1", "r1:invasion:2"]
    state.disciples[0].injury_stacks = 1
    state.disciples[0].injured_until = NOW + timedelta(hours=3)
    slot = await create_slot(state)
    original, revision = await saved(factory, slot)
    started = await client.post(f"/api/saves/{slot}/world/start", json={
        "revision": revision, "node_id": node_id, "party": ["hero"], "practice": True,
    })
    assert started.status_code == 200
    ended = await finish_run(client, slot, started.json())
    assert ended["status"] == ("cleared" if strong else "defeated")
    assert ended["run"]["pending_gear"] == []
    response = await client.post(f"/api/saves/{slot}/run/settle", json={"revision": ended["revision"]})
    assert response.status_code == 200
    content = response.json()
    assert content["loot"] == {} and content["gear"] == []
    current = content["state"]
    assert current["resources"] == original["resources"]
    assert current["inventory"] == original["inventory"]
    assert current["world"] == original["world"]
    assert current["gear"] == original["gear"]
    assert current["disciples"][0]["injury_stacks"] == 1
    assert current["disciples"][0]["injured_until"] == state.disciples[0].injured_until.isoformat().replace("+00:00", "Z")
    assert current["last_run_review"]["practice"]


def test_second_region_tower_does_not_unlock_first_region_tier_two():
    state = GameState(
        equipment_version=1, resources=Resources(stamina=3), facility_levels={"tower": 2},
        disciples=[DiscipleState(id="hero", template_id="test")],
    )
    state.world.current_region = 2
    state.world.unlocked_regions = [1, 2]
    state.world.tower_records = {"1": {}, "2": {}}
    mode = deepcopy(load_modes()["tower"])
    mode.update(
        node_count=20, boss_every=20, choices_per_step=1, elite_chance=0, enemy_growth=0,
        encounters={kind: ["weak"] for kind in ("battle", "elite", "boss")}, encounter_variants={},
        kind_stat_multiplier={kind: 1 for kind in ("battle", "elite", "boss")},
    )
    assert run_engine.start_run(
        state, ["hero"], TEMPLATES, mode, NOW, seed=2,
        skills={}, enemies=ENEMIES, affix_pool=[], weapons={}, route_version=2,
    ) is None
    for _ in range(20):
        assert run_engine.choose(state, 0) is None
    assert run_engine.run_status(state.active_run) == "cleared"
    run_engine.settle_run(state, mode, NOW)
    assert state.world.tower_records["2"] == {"1": 20}
    assert state.world.tower_records["1"] == {}
    assert travel_region(state, 1, NOW, load_world()) is None
    assert state.tower_tiers == {}
    error = run_engine.start_run(
        state, ["hero"], TEMPLATES, mode, NOW, seed=2, tower_tier=2,
        skills={}, enemies=ENEMIES, affix_pool=[], weapons={}, route_version=2,
    )
    assert error == "请先通关前一阶问道塔"


@pytest.mark.parametrize(("mode_id", "world_node_id"), [
    ("dungeon", "r1:dungeon:1:1"), ("tower", None), ("tower", "r1:tower"),
])
async def test_defeat_recovers_dropped_gear_exactly_once_with_existing_resource_policy(world_client, mode_id, world_node_id):
    client, factory, create_slot = world_client
    state = start_staged_run(mode_id=mode_id, world_node_id=world_node_id)
    assert run_engine.choose(state, 0) is None
    assert state.active_run.last_battle.won
    assert len(state.active_run.pending_gear) == 1
    pending = deepcopy(state.active_run.pending_gear[0])
    loot = dict(state.active_run.pending_loot)
    assert pending.id not in state.gear
    assert run_engine.choose(state, 0) is None
    assert run_engine.run_status(state.active_run) == "defeated"
    expected_loot = loot if mode_id == "dungeon" else run_engine.defeat_loot(
        loot, len(state.active_run.nodes), state.active_run.party_snapshot.mode,
    )
    expected_loot[MATERIAL] = int(expected_loot[MATERIAL])
    slot = await create_slot(state)
    stored, revision = await saved(factory, slot)
    refreshed = (await client.get(f"/api/saves/{slot}/run")).json()
    assert refreshed["run"]["pending_gear"][0] == pending.model_dump(mode="json")
    assert (await client.get(f"/api/saves/{slot}/equipment")).json()["items"] == []
    response = await client.post(f"/api/saves/{slot}/run/settle", json={"revision": revision})
    assert response.status_code == 200
    result = response.json()
    assert result["victory"] is False
    assert result["loot"] == expected_loot
    assert result["gear"] == [pending.model_dump(mode="json")]
    assert result["state"]["gear"][pending.id] == pending.model_dump(mode="json")
    assert result["state"]["resources"]["cultivation"] == stored["resources"]["cultivation"] + expected_loot["cultivation"]
    assert result["state"]["inventory"][MATERIAL] == int(expected_loot[MATERIAL])
    assert result["state"]["disciples"][0]["injury_stacks"] == 1
    assert result["state"]["active_run"] is None
    if mode_id == "tower":
        assert result["state"]["tower_tiers"] == {"1": 1}
        assert result["state"]["world"]["tower_records"]["1"] == {"1": 1}
    after = await saved(factory, slot)
    assert (await client.post(f"/api/saves/{slot}/run/settle", json={"revision": revision})).status_code == 409
    assert (await client.post(f"/api/saves/{slot}/run/settle", json={"revision": after[1]})).status_code == 400
    assert await saved(factory, slot) == after


def test_run_freezes_equipped_stats_and_drop_rules_before_config_changes(monkeypatch):
    rules = deepcopy(load_equipment())
    rules["growth_per_level"] = .25
    for definition in rules["definitions"]:
        definition["value"] = .2
    monkeypatch.setattr(run_engine, "load_equipment", lambda: rules)
    state = GameState(
        equipment_version=1, resources=Resources(stamina=3),
        disciples=[DiscipleState(id="hero", template_id="test", gear_slots={"weapon": "owned"})],
        gear={"owned": GearItem(id="owned", definition_id="test", name="佩剑", slot="weapon", main_stat="atk", main_value=.2)},
    )
    start_staged_run(state)
    initial = state.active_run.party_snapshot.combatants[0].model_dump()
    assert initial["attack"] == 30
    assert "出征" in upgrade_gear(state, "owned", load_equipment())
    for definition in rules["definitions"]:
        definition["value"] = 999
    rules["growth_per_level"] = 99
    state.gear["owned"].main_value = 999
    assert run_engine.choose(state, 0) is None
    assert state.active_run.party_snapshot.combatants[0].model_dump() == initial
    drop = state.active_run.pending_gear[0]
    assert drop.main_value == .2 and drop.growth_per_level == .25
    assert drop.id not in state.gear


def test_equipment_changes_real_personal_combat_and_duty_without_buffing_other_disciple():
    hero = DiscipleState(id="hero", template_id="test")
    companion = DiscipleState(id="companion", template_id="test")
    state = GameState(
        equipment_version=1, resources=Resources(stamina=3), disciples=[hero, companion],
        duty_slots=[DutySlot(disciple_id=d.id, assigned_at=NOW) for d in (hero, companion)],
        gear={
            "weapon": GearItem(id="weapon", definition_id="test", name="佩剑", slot="weapon", main_stat="atk", main_value=.2, affix="damage", affix_value=.1),
            "ring": GearItem(id="ring", definition_id="test", name="聚灵戒", slot="ring", main_stat="cultivation_rate", main_value=.5),
        },
    )
    assert equip_gear(state, "weapon", "hero") is None
    assert equip_gear(state, "ring", "hero") is None
    first = personal_duty_rates(hero, TEMPLATES["test"], equipment_bonuses=combat_equipment_bonuses(state, hero))
    second = personal_duty_rates(companion, TEMPLATES["test"], equipment_bonuses=combat_equipment_bonuses(state, companion))
    assert first["cultivation_rate"] == pytest.approx(.075)
    assert second["cultivation_rate"] == pytest.approx(.05)
    assert rates_of(state, TEMPLATES)["cultivation_rate"] == pytest.approx(.125)
    trained = preview(state, hero, TEMPLATES["test"], {}, {}).current
    start_staged_run(state)
    first_unit, second_unit = state.active_run.party_snapshot.combatants
    assert first_unit.attack == trained.attack == 30
    assert second_unit.attack == 25
    assert first_unit.bonuses["damage"] == .1
    assert "damage" not in second_unit.bonuses
    assert hero.bonuses == companion.bonuses == state.bonuses == {}


async def test_equipping_yield_gear_settles_old_interval_before_new_personal_rate(world_client):
    client, factory, create_slot = world_client
    state = real_state()
    old = NOW - timedelta(hours=2)
    state.disciples[0].bonuses = {}
    state.duty_slots = [DutySlot(disciple_id="hero", assigned_at=old)]
    state.gear["ring"] = GearItem(
        id="ring", definition_id="legacy", name="聚灵佩", slot="ring", main_stat="cultivation_rate", main_value=1,
    )
    from app.config_loader import load_disciples

    record_event(state, load_disciples(), old, {})
    old_rate = rates_of(state, load_disciples())["cultivation_rate"]
    slot = await create_slot(state, old)
    _, revision = await saved(factory, slot)
    response = await client.post(f"/api/saves/{slot}/equipment", json={
        "revision": revision, "action": "equip", "item_id": "ring", "disciple_id": "hero",
    })
    assert response.status_code == 200
    content = response.json()
    assert content["state"]["resources"]["cultivation"] == pytest.approx(2 * (1 + old_rate))
    assert content["production"]["cultivation"] == pytest.approx(1 + 2 * old_rate)
    assert content["state"]["duty_events"][-1]["rates"]["cultivation_rate"] == pytest.approx(2 * old_rate)


async def test_legacy_equipment_migrates_after_old_income_and_rollback_keeps_anchor(world_client, monkeypatch):
    client, factory, create_slot = world_client
    state = real_state()
    state.equipment_version = 0
    state.crafted_recipes = ["ju_ling_pei"]
    state.bonuses = {"cultivation_rate": .15}
    slot = await create_slot(state, NOW - timedelta(hours=2))
    _, revision = await saved(factory, slot)
    settled = await client.post(f"/api/saves/{slot}/settle", json={"revision": revision})
    assert settled.status_code == 200
    result = settled.json()
    assert result["state"]["resources"]["cultivation"] == pytest.approx(2.3)
    assert result["state"]["bonuses"] == {}
    assert result["state"]["equipment_version"] == 1
    assert len(result["state"]["gear"]) == 1
    item_id = next(iter(result["state"]["gear"]))
    again = await client.post(f"/api/saves/{slot}/settle", json={"revision": result["revision"]})
    assert again.status_code == 200
    current = again.json()
    assert current["state"]["resources"] == result["state"]["resources"]
    assert current["state"]["gear"] == result["state"]["gear"]

    class RollbackDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW - timedelta(hours=1)

    monkeypatch.setattr(state_api, "datetime", RollbackDateTime)
    equipped = await client.post(f"/api/saves/{slot}/equipment", json={
        "revision": current["revision"], "action": "equip", "item_id": item_id, "disciple_id": "hero",
    })
    assert equipped.status_code == 200
    assert equipped.json()["state"]["resources"] == current["state"]["resources"]
    assert len(equipped.json()["state"]["gear"]) == 1
    async with factory() as session:
        assert await SaveRepository(session).get_last_settled_at(slot) == NOW


async def test_ascension_consumes_one_token_and_travel_keeps_garrisons_and_tower_history(world_client):
    client, factory, create_slot = world_client
    state = real_state()
    state.inventory["sheng_xian_ling"] = 2
    state.world.cleared_nodes = [f"r1:{kind}:{area}" for area in range(1, 4) for kind in ("gate", "invasion")]
    state.world.unlocked_areas["1"] = 3
    state.tower_tiers = {"1": 20, "2": 5}
    state_api.initialize_world(state, NOW)
    state.sects[0].conquered = True
    state.sects[0].garrison = [DutySlot(disciple_id="hero", assigned_at=NOW)]
    slot = await create_slot(state)
    original = (await client.get(f"/api/saves/{slot}/world")).json()
    command = {"revision": original["revision"]}
    response = await client.post(f"/api/saves/{slot}/world/ascend", json=command)
    assert response.status_code == 200, response.text
    ascended = response.json()
    assert ascended["state"]["inventory"]["sheng_xian_ling"] == 1
    assert ascended["state"]["world"]["current_region"] == 2
    assert ascended["state"]["tower_tiers"] == {}
    assert ascended["production"]["garrisons"] == original["production"]["garrisons"]
    assert (await client.post(f"/api/saves/{slot}/world/ascend", json=command)).status_code == 409
    assert (await client.post(f"/api/saves/{slot}/world/ascend", json={"revision": ascended["revision"]})).status_code == 400
    travel = {"revision": ascended["revision"], "region_id": 1}
    returned = await client.post(f"/api/saves/{slot}/world/travel", json=travel)
    assert returned.status_code == 200
    content = returned.json()
    assert content["state"]["tower_tiers"] == {"1": 20, "2": 5}
    assert content["state"]["inventory"]["sheng_xian_ling"] == 1
    original_sect = next(sect for sect in original["state"]["sects"] if sect["id"] == "sect_1")
    returned_sect = next(sect for sect in content["state"]["sects"] if sect["id"] == "sect_1")
    assert returned_sect["garrison"] == original_sect["garrison"]
    assert returned_sect["conquered"]
    assert content["production"]["garrisons"] == original["production"]["garrisons"]
    after = await saved(factory, slot)
    assert (await client.post(f"/api/saves/{slot}/world/travel", json=travel)).status_code == 409
    assert await saved(factory, slot) == after
