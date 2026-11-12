"""真实自动战斗边界：技能目标、联动条件、护盾、回合上限与六人出征。"""

from datetime import datetime, timezone

from app.domain.battle import simulate_battle
from app.domain.run_engine import start_run, choose, run_status, pick_affix
from app.models.battle import BattleAction, BattleBond, BattleUnit, SkillDefinition
from app.models.save import DiscipleState, GameState, Resources
from app.config_loader import load_disciples, load_modes


def unit(key, *, slot=0, hp=100, atk=10, defense=0, speed=10, actions=None, cooldown=3, passive=None):
    return BattleUnit(
        id=key, template_id=key, name=key, slot=slot, health=hp, attack=atk, defense=defense,
        speed=speed, active=SkillDefinition(id=f"{key}-art", name=key, type="active", cooldown=cooldown, actions=actions or []),
        passive=SkillDefinition(id=f"{key}-passive", name="被动", type="passive", **(passive or {})),
    )


def test_skill_targets_are_fixed_and_dead_target_is_not_replaced():
    hero = unit("hero", atk=100, actions=[BattleAction(kind="damage", target="enemy_first"), BattleAction(kind="buff", target="enemy_first", stat="def", value=-.25)])
    result = simulate_battle([hero], [unit("first", hp=5, speed=1), unit("second", slot=1, hp=500, speed=1)], {})
    opening = result.events[0]
    assert [effect.target_id for effect in opening.effects] == ["first"]
    assert not next(state for state in opening.units if state.id == "second").statuses


def test_condition_does_not_see_its_own_new_weakened_state():
    hero = unit("hero", atk=10, actions=[BattleAction(kind="buff", target="enemy_first", stat="def", value=-.25), BattleAction(kind="damage", target="enemy_first")], passive={"condition": "target_weakened", "bonuses": {"damage": 1}})
    result = simulate_battle([hero], [unit("enemy", hp=500, atk=1, defense=100, speed=1)], {})
    damage = [effect for effect in result.events[0].effects if effect.kind == "damage"][0]
    assert damage.amount == 5  # 本次降防生效于公式，但不能追溯激活条件被动。
    later = next(event for event in result.events if event.actor_id == "hero" and event.round == 2)
    assert later.effects[0].amount == 11


def test_unchanged_same_source_shield_falls_back_without_spending_cooldown():
    hero = unit("hero", hp=200, atk=20, cooldown=1, actions=[BattleAction(kind="shield", target="self", coefficient=1, duration=10)])
    # 敌方专注增益不会消耗盾，第二次行动不能原样空放。
    enemy = unit("enemy", hp=1000, atk=1, speed=1, cooldown=1, actions=[BattleAction(kind="buff", target="self", stat="def", value=.1)])
    result = simulate_battle([hero], [enemy], {})
    actions = [event for event in result.events if event.actor_id == "hero"]
    assert actions[0].skill_id == "hero-art"
    assert actions[1].skill_id == "basic_attack"
    assert actions[1].units[0].cooldown == 0


def test_round_limit_keeps_survivor_health_and_bounds_action_count():
    left = [unit(f"a{i}", slot=i, hp=100000, atk=1) for i in range(6)]
    right = [unit(f"e{i}", slot=i, hp=100000, atk=1) for i in range(6)]
    result = simulate_battle(left, right, {})
    assert result.reason == "round_limit" and not result.won
    assert result.rounds == 20 and len(result.events) == 240
    assert all(state.hp > 0 for state in result.final_units)


def test_bond_extra_shield_has_own_source_and_never_creates_extra_turn():
    healer = unit("healer", actions=[BattleAction(kind="heal", target="ally_lowest", coefficient=1)])
    archer = unit("archer", slot=1)
    bond = BattleBond(id="pair", name="配合", members=["healer", "archer"], requires=2, modifiers=[{"skill": "healer-art", "extra_actions": [{"kind": "shield", "target": "ally_template", "target_template": "archer", "coefficient": 2}]}])
    result = simulate_battle([healer, archer], [unit("enemy", hp=200, speed=1)], {"healer": 50}, [bond])
    opening = result.events[0]
    assert opening.bonds == ["pair"]
    assert len(opening.effects) == 2
    assert opening.effects[1].kind == "shield" and ":pair:" in opening.effects[1].source
    assert len([event for event in result.events if event.round == 1 and event.actor_id == "healer"]) == 1


def test_six_members_are_allowed_but_seven_and_duplicates_are_rejected():
    keys = list(load_disciples())[:7]
    state = GameState(resources=Resources(stamina=3), disciples=[DiscipleState(id=key, template_id=key) for key in keys])
    now = datetime.now(timezone.utc)
    assert "1 到 6" in start_run(state, keys, load_disciples(), load_modes()["tower"], now)
    assert "重复" in start_run(state, [keys[0], keys[0]], load_disciples(), load_modes()["tower"], now)
    assert start_run(state, keys[:6], load_disciples(), load_modes()["tower"], now, seed=1) is None
    assert len(state.active_run.member_hp) == 6
    assert state.active_run.hp == sum(state.active_run.member_hp.values())


def test_round_limit_run_is_ended_even_when_aggregate_hp_is_positive():
    template = {"hero": {"id": "hero", "base_stats": {"hp": 100000, "atk": 1, "def": 1, "spd": 1}}}
    enemy = {"dummy": {"id": "dummy", "name": "木桩", "base_stats": {"hp": 100000, "atk": 1, "def": 1, "spd": 1}}}
    mode = {**load_modes()["tower"], "encounters": {"battle": ["dummy"], "elite": ["dummy"], "boss": ["dummy"]}}
    state = GameState(resources=Resources(stamina=3), disciples=[DiscipleState(id="hero", template_id="hero")])
    start_run(state, ["hero"], template, mode, datetime.now(timezone.utc), seed=1, enemies=enemy, affix_pool=[], skills={})
    assert choose(state, 0) is None
    assert state.active_run.hp > 0 and state.active_run.end_reason == "round_limit"
    assert run_status(state.active_run) == "defeated"
    assert "已结束" in choose(state, 0)


def test_max_health_affix_keeps_ratio_and_does_not_revive():
    keys = list(load_disciples())[:2]
    state = GameState(resources=Resources(stamina=3), disciples=[DiscipleState(id=key, template_id=key) for key in keys])
    affix = {"id": "health", "group": "g", "effects": [{"stat": "hp", "scope": "run", "mode": "add_pct", "value": 1}]}
    start_run(state, keys, load_disciples(), load_modes()["tower"], datetime.now(timezone.utc), seed=1, affix_pool=[affix])
    run = state.active_run
    run.member_hp[keys[0]] = 0
    run.member_hp[keys[1]] = 10
    run.affix_pending = True
    run.affix_options = ["health"]
    assert pick_affix(state, "health") is None
    assert run.member_hp == {keys[0]: 0, keys[1]: 20}


def test_heal_is_capped_shields_expire_and_absorb_before_health():
    protector = unit("protector", hp=100, atk=10, cooldown=20, actions=[BattleAction(kind="shield", target="self", coefficient=2, duration=1)])
    enemy = unit("enemy", hp=500, atk=5, speed=1)
    result = simulate_battle([protector], [enemy], {})
    first_hit = next(event for event in result.events if event.actor_id == "enemy")
    assert first_hit.effects[0].absorbed == 4 and first_hit.effects[0].amount == 0
    second_hit = next(event for event in result.events if event.actor_id == "enemy" and event.round == 2)
    assert second_hit.effects[0].absorbed == 0 and second_hit.effects[0].amount == 4
    healer = unit("healer", atk=100, actions=[BattleAction(kind="heal", target="ally_lowest", coefficient=2)])
    healed = simulate_battle([healer], [enemy], {"healer": 95})
    assert healed.events[0].effects[0].amount == 5
    assert healed.events[0].units[0].hp == 100


def test_cooldown_uses_personal_actions_and_resets_between_battles():
    hero = unit("hero", hp=1000, atk=1, cooldown=3, actions=[BattleAction(kind="damage", target="enemy_first", coefficient=2)])
    enemy = unit("enemy", hp=1000, atk=1, speed=1)
    result = simulate_battle([hero], [enemy], {})
    own = [event for event in result.events if event.actor_id == "hero"]
    assert [event.skill_id for event in own[:4]] == ["hero-art", "basic_attack", "basic_attack", "hero-art"]
    again = simulate_battle([hero], [enemy], {"hero": 900})
    assert again.events[0].skill_id == "hero-art" and again.initial_units[0].shield == 0
