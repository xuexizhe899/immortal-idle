"""宗门生成、擂台轮换、固定快照、首胜结算与塔阶门槛。"""

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app.config_loader import load_bonds, load_disciples, load_enemies, load_modes, load_sects
from app.domain import conquest
from app.domain.run_engine import choose, run_status, settle_run, start_run
from app.models.save import BattleSummary, DiscipleState, DutySlot, GameState, Resources, RunNode

NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)
PARTY = ["guanyu", "zhangfei", "zhaoyun", "zhugeliang", "yuefei", "baisuzhen"]


def make_state():
    state = GameState(resources=Resources(stamina=6), rng_seed=71, disciples=[
        DiscipleState(id=key, template_id=key, level=20, realm=3) for key in PARTY
    ])
    conquest.ensure_sects(state, load_sects(), load_enemies())
    return state


def start(state, party=None, target=0):
    return start_run(state, party or PARTY, load_disciples(), load_modes()["expedition"], NOW,
                     seed=18, bonds=load_bonds(), sect=state.sects[target], route_version=2)


def test_generation_is_stable_extends_by_level_and_covers_special_resources():
    state = make_state()
    original = deepcopy(state.sects)
    assert len(state.sects) == 3
    assert all(unit.asset_id for sect in state.sects for team in sect.arena_teams for unit in team)
    assert all(sect.leader.asset_id for sect in state.sects)
    assert {sect.special_material_id for sect in state.sects} == {"gong_fa_qi_pei", "hu_chi_qi_pei", "po_jing_ling_cai"}
    assert not conquest.ensure_sects(state, load_sects(), load_enemies())
    state.facility_levels["hall"] = 3
    assert conquest.ensure_sects(state, load_sects(), load_enemies())
    assert len(state.sects) == 9 and state.sects[:3] == original
    styles = {style["name"]: style for style in load_sects()["styles"]}
    for sect in state.sects:
        style = styles[sect.style]
        for team in sect.arena_teams:
            for unit in team:
                assert unit.asset_id == style["disciple_assets"][unit.template_id]
        assert sect.leader.asset_id == style["leader_asset_id"]
        assert sect.leader.asset_id not in style["disciple_assets"].values()
    restored = GameState.model_validate_json(state.model_dump_json())
    assert not conquest.ensure_sects(restored, load_sects(), load_enemies())
    assert restored.sects == state.sects
    regenerated = GameState(rng_seed=71, facility_levels={"hall": 3})
    conquest.ensure_sects(regenerated, load_sects(), load_enemies())
    assert regenerated.sects == state.sects


def sect_art_config():
    config = deepcopy(load_sects())
    for style in config["styles"]:
        style["disciple_assets"] = {
            key: f"art-foundation/sects/{style['id']}_{key}"
            for team in style["teams"] for key in team
        }
        style["leader_asset_id"] = f"art-foundation/sects/{style['id']}_master"
    return config


def test_sect_portraits_follow_style_and_role_through_battle_snapshot():
    state = make_state()
    state.sects = []
    config = sect_art_config()
    conquest.ensure_sects(state, config, load_enemies())
    for sect, style in zip(state.sects, config["styles"]):
        for team in sect.arena_teams:
            for unit in team:
                assert unit.asset_id == style["disciple_assets"][unit.template_id]
        assert sect.leader.asset_id == style["leader_asset_id"]
        assert sect.leader.asset_id not in style["disciple_assets"].values()
    assert start(state) is None
    assert conquest.arena(state, PARTY[:3]) is None
    foes = [unit for unit in state.active_run.last_battle.initial_units if unit.side == "enemy"]
    assert [unit.asset_id for unit in foes] == [unit.asset_id for unit in state.sects[0].arena_teams[0]]
    state.active_run.guard = 0
    assert conquest.arena(state, PARTY[:3]) is None
    leader = next(unit for unit in state.active_run.last_battle.initial_units if unit.side == "enemy")
    assert leader.asset_id == config["styles"][0]["leader_asset_id"]


def test_legacy_sect_portraits_upgrade_without_changing_rules_or_active_run():
    state = make_state()
    for sect in state.sects:
        sect.arena_teams = [[unit.model_copy(update={
            "asset_id": f"art-foundation/enemies/{unit.template_id}",
        }) for unit in team] for team in sect.arena_teams]
        sect.leader = sect.leader.model_copy(update={"asset_id": f"art-foundation/enemies/{sect.leader.template_id}"})
    state.sects[0].arena_teams[0][0] = state.sects[0].arena_teams[0][0].model_copy(update={"asset_id": ""})
    state.sects[1].leader = state.sects[1].leader.model_copy(update={"asset_id": "custom/ward_master"})
    state.sects[2].conquered = True
    state.sects[2].garrison = [DutySlot(disciple_id=PARTY[-1], assigned_at=NOW)]
    assert start(state, PARTY[:3]) is None
    assert conquest.arena(state, PARTY[:3]) is None
    before = deepcopy(state)
    config = sect_art_config()
    assert conquest.ensure_sects(state, config, load_enemies())
    assert state.model_dump(exclude={"sects"}) == before.model_dump(exclude={"sects"})
    for sect, old, style in zip(state.sects, before.sects, config["styles"]):
        assert sect.model_dump(exclude={"arena_teams", "leader"}) == old.model_dump(exclude={"arena_teams", "leader"})
        for team, old_team in zip(sect.arena_teams, old.arena_teams):
            for unit, old_unit in zip(team, old_team):
                assert unit.model_dump(exclude={"asset_id"}) == old_unit.model_dump(exclude={"asset_id"})
                assert unit.asset_id == style["disciple_assets"][unit.template_id]
        assert sect.leader.model_dump(exclude={"asset_id"}) == old.leader.model_dump(exclude={"asset_id"})
        expected = "custom/ward_master" if sect.style == "御守" else style["leader_asset_id"]
        assert sect.leader.asset_id == expected
    upgraded = state.model_dump_json()
    assert not conquest.ensure_sects(state, config, load_enemies())
    assert state.model_dump_json() == upgraded
    # 同一征讨后续战报也维持旧快照，换图不能改变本局战斗输入。
    assert conquest.arena(state, PARTY[:3]) is None
    assert conquest.arena(before, PARTY[:3]) is None
    assert state.active_run == before.active_run


def test_two_perfect_arenas_unlock_boss_and_settlement_conquers_once():
    state = make_state()
    assert start(state) is None
    run = state.active_run
    assert run.guard == 100 and run.choices == [] and run.affix_options == []
    assert state.resources.stamina == 4
    assert conquest.arena(state, PARTY[:3]) is None
    assert run.guard == 50 and run.arena_round == 1
    first_hp = dict(run.member_hp)
    assert conquest.arena(state, PARTY[3:]) is None
    assert run.guard == 0 and run.arena_round == 2 and run.end_reason is None
    assert {key: run.member_hp[key] for key in PARTY[:3]} == {key: first_hp[key] for key in PARTY[:3]}
    assert conquest.arena(state, PARTY[:3]) is None
    assert run.last_battle.node.kind == "boss"
    assert len([unit for unit in run.last_battle.initial_units if unit.side == "enemy"]) == 1
    assert run_status(run) == "cleared" and not state.sects[0].conquered
    before = deepcopy(state.resources)
    loot = dict(run.pending_loot)
    result = settle_run(state, {}, NOW)
    assert result["loot"] == loot and result["victory"]
    assert state.sects[0].conquered and state.active_run is None
    assert state.last_run_review.sect_id == state.sects[0].id
    assert state.last_run_review.sect_name == state.sects[0].name
    assert state.resources.reputation == before.reputation + loot["reputation"]
    assert all(not d.busy and not d.injury_stacks for d in state.disciples)
    assert "已攻克" in start(state)


def test_invalid_selection_and_small_party_do_not_change_state():
    state = make_state()
    before = state.model_dump_json()
    assert "3 到 6" in start(state, PARTY[:2])
    assert state.model_dump_json() == before
    assert start(state) is None
    before = state.model_dump_json()
    for party in (PARTY[:2], [PARTY[0]] * 3, [*PARTY[:2], "missing"]):
        assert conquest.arena(state, party)
        assert state.model_dump_json() == before
    assert "三名" in choose(state, 0)


def test_reload_and_changed_permanent_state_do_not_change_arena_result():
    state = make_state()
    start(state)
    assert conquest.arena(state, PARTY[:3]) is None
    restored = GameState.model_validate_json(state.model_dump_json())
    restored.sects[0].arena_teams = list(reversed(restored.sects[0].arena_teams))
    restored.sects[0].leader.active.cooldown = 20
    restored.sects[0].loot["reputation"] = 99999
    restored.disciples[0].level = 1
    for party in (PARTY[3:], PARTY[:3]):
        assert conquest.arena(state, party) is None
        assert conquest.arena(restored, party) is None
        assert state.active_run == restored.active_run


@pytest.mark.parametrize("survivors,damage", [(3, 50), (2, 30), (1, 15)])
def test_guard_uses_actual_winning_survivors(monkeypatch, survivors, damage):
    state = make_state()
    start(state)
    actual_battle = conquest.simulate_battle

    def prescribed_outcome(*args):
        result = actual_battle(*args)
        allies = [unit for unit in result.final_units if unit.side == "ally"]
        for unit in allies[survivors:]:
            unit.hp = 0
        return result

    monkeypatch.setattr(conquest, "simulate_battle", prescribed_outcome)
    assert conquest.arena(state, PARTY[:3]) is None
    assert state.active_run.guard == 100 - damage
    assert state.active_run.member_hp[PARTY[2]] == (0 if survivors < 3 else state.active_run.last_battle.final_units[2].hp)


def test_three_narrow_wins_fail_guard_and_only_deployed_receive_injury(monkeypatch):
    state = make_state()
    start(state)
    actual_battle = conquest.simulate_battle

    def one_down(*args):
        result = actual_battle(*args)
        next(unit for unit in result.final_units if unit.side == "ally").hp = 0
        return result

    monkeypatch.setattr(conquest, "simulate_battle", one_down)
    for party in (PARTY[:3], PARTY[1:4], PARTY[2:5]):
        assert conquest.arena(state, party) is None
    run = state.active_run
    assert run.guard == 10 and run.arena_round == 3
    assert run.end_reason == "guard_unbroken" and run_status(run) == "defeated"
    result = settle_run(state, {}, NOW)
    assert not result["victory"] and not result["loot"] and not state.sects[0].conquered
    assert [d.injury_stacks for d in state.disciples] == [1, 1, 1, 1, 1, 0]
    assert start(state) is None and state.active_run.guard == 100


def test_lost_arena_can_continue_with_reserves_and_dead_cannot_return(monkeypatch):
    state = make_state()
    start(state)
    actual_battle = conquest.simulate_battle

    def wipe_selected(*args):
        result = actual_battle(*args)
        result.won = False
        result.reason = "defeated"
        for unit in result.final_units:
            if unit.side == "ally":
                unit.hp = 0
        return result

    monkeypatch.setattr(conquest, "simulate_battle", wipe_selected)
    conquest.arena(state, PARTY[:3])
    assert state.active_run.guard == 100 and run_status(state.active_run) == "choosing_node"
    assert "倒下" in conquest.arena(state, PARTY[:3])
    monkeypatch.setattr(conquest, "simulate_battle", actual_battle)
    assert conquest.arena(state, PARTY[3:]) is None
    assert conquest.arena(state, PARTY[3:]) is None
    assert state.active_run.guard == 0


def test_retreat_before_battle_preserves_injuries_and_returns_original_duty():
    state = make_state()
    state.duty_slots = [DutySlot(disciple_id=PARTY[0], assigned_at=NOW)]
    assert start(state) is None
    assert not state.duty_slots and state.active_run.return_posts == {PARTY[0]: "home"}
    assert conquest.retreat(state) is None
    result = settle_run(state, {}, NOW)
    assert result["loot"] == {} and state.resources.stamina == 4
    assert all(d.injury_stacks == 0 for d in state.disciples)
    assert state.duty_slots[0].disciple_id == PARTY[0]


def test_broken_guard_does_not_allow_boss_with_only_two_fighters(monkeypatch):
    state = make_state()
    start(state, PARTY[:3])
    state.active_run.guard = 30
    actual_battle = conquest.simulate_battle

    def two_survivors(*args):
        result = actual_battle(*args)
        next(unit for unit in result.final_units if unit.side == "ally").hp = 0
        return result

    monkeypatch.setattr(conquest, "simulate_battle", two_survivors)
    conquest.arena(state, PARTY[:3])
    assert state.active_run.guard == 0
    assert state.active_run.end_reason == "insufficient_fighters"
    assert run_status(state.active_run) == "defeated"
    assert conquest.arena(state, PARTY[:3]) == "征讨已结束，请结算"


def test_arena_timeout_with_three_alive_can_continue(monkeypatch):
    state = make_state()
    start(state, PARTY[:3])
    actual_battle = conquest.simulate_battle

    def timeout(*args):
        result = actual_battle(*args)
        result.won = False
        result.reason = "round_limit"
        return result

    monkeypatch.setattr(conquest, "simulate_battle", timeout)
    conquest.arena(state, PARTY[:3])
    assert state.active_run.guard == 100 and state.active_run.arena_round == 1
    assert state.active_run.end_reason is None
    assert run_status(state.active_run) == "choosing_node"
    monkeypatch.setattr(conquest, "simulate_battle", actual_battle)
    conquest.arena(state, PARTY[:3])
    conquest.arena(state, PARTY[:3])
    assert state.active_run.guard == 0 and state.active_run.end_reason is None


def test_tower_tier_requires_facility_and_previous_clear_and_freezes_scaling():
    state = make_state()
    mode = load_modes()["tower"]
    assert "升级" in start_run(state, PARTY, load_disciples(), mode, NOW, tower_tier=2)
    state.facility_levels["tower"] = 2
    assert "前一阶" in start_run(state, PARTY, load_disciples(), mode, NOW, tower_tier=2)
    state.tower_floor = 20
    state.facility_levels["tower"] = 3
    assert start_run(state, PARTY, load_disciples(), mode, NOW, tower_tier=2, seed=8, route_version=2) is None
    run = state.active_run
    assert run.tower_tier == 2
    assert run.party_snapshot.mode["kind_stat_multiplier"]["battle"] == 1.6
    assert run.party_snapshot.mode["rewards"]["battle"]["cultivation"] == 15
    assert mode["kind_stat_multiplier"]["battle"] == 1
    run.nodes = [RunNode(kind="battle", enemy="test", power=0)] * 20
    settle_run(state, {}, NOW)
    assert state.tower_tiers["2"] == 20
    assert state.last_run_review.tower_tier == 2
    assert start_run(state, PARTY, load_disciples(), mode, NOW, seed=9, tower_tier=3) is None


def test_legacy_tower_clear_is_not_lost_after_failed_tier_one_run():
    state = make_state()
    state.tower_floor = 20
    state.facility_levels["tower"] = 2
    mode = load_modes()["tower"]
    start_run(state, PARTY, load_disciples(), mode, NOW, seed=1)
    state.active_run.hp = 0
    state.active_run.nodes = [RunNode(kind="battle", enemy="test", power=0)]
    settle_run(state, {}, NOW)
    assert state.tower_tiers["1"] == 20
    assert start_run(state, PARTY, load_disciples(), mode, NOW, seed=2, tower_tier=2) is None


def test_losing_twentieth_floor_does_not_unlock_next_tier():
    state = make_state()
    state.facility_levels["tower"] = 2
    mode = load_modes()["tower"]
    start_run(state, PARTY, load_disciples(), mode, NOW, seed=1)
    run = state.active_run
    node = RunNode(kind="boss", enemy="final", power=1)
    run.nodes = [node] * 20
    run.end_reason = "round_limit"
    run.last_battle = BattleSummary(
        id="final", node=node, party_power=1, enemy_power=1, hp_before=100, hp_after=50,
        damage=50, won=False, reason="round_limit",
    )
    settle_run(state, {}, NOW)
    assert state.tower_floor == state.tower_tiers["1"] == 19
    assert "前一阶" in start_run(state, PARTY, load_disciples(), mode, NOW, seed=2, tower_tier=2)
