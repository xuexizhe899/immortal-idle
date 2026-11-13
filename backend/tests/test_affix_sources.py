"""道法来源随真实效果输出，并保留固定定义及各乘区的截断结果。"""

from datetime import datetime, timezone

import pytest

from app.domain.battle import simulate_battle
from app.domain.run_engine import start_run, with_affixes
from app.models.battle import BattleEffectResult, BattleUnit, SkillDefinition
from app.models.save import DiscipleState, GameState, Resources


def combatants(affixes, actions=None):
    state = GameState(resources=Resources(stamina=3), disciples=[DiscipleState(id="hero", template_id="hero")])
    templates = {"hero": {"id": "hero", "base_stats": {"hp": 1000, "atk": 100, "def": 0, "spd": 20}, "skill": "art"}}
    skills = {"art": {"id": "art", "name": "施法", "type": "active", "actions": actions or []}}
    mode = {"id": "tower", "stamina_cost": 1, "node_count": 20, "base_enemy_power": 1, "enemy_growth": 0,
            "choices_per_step": 1, "elite_chance": 0, "boss_every": 5, "reward_growth": 0,
            "rewards": {"battle": {}}, "encounters": {"battle": ["foe"], "elite": ["foe"], "boss": ["foe"]}}
    enemy = {"foe": {"id": "foe", "name": "敌人", "base_stats": {"hp": 10000, "atk": 100, "def": 0, "spd": 1}}}
    assert start_run(state, ["hero"], templates, mode, datetime(2026, 11, 13, tzinfo=timezone.utc),
                     seed=1, affix_pool=affixes, enemies=enemy, skills=skills) is None
    state.active_run.affixes = [item["id"] for item in affixes]
    hero = with_affixes(state.active_run)[0]
    foe = BattleUnit(id="foe", template_id="foe", name="敌人", slot=0, health=10000, attack=100,
                     defense=0, speed=1, active=SkillDefinition(id="foe-art", name="敌招", type="active"),
                     passive=SkillDefinition(id="foe-passive", name="无", type="passive"))
    return state, hero, foe


def test_conditional_sources_only_record_matching_condition_and_bonus_key():
    affixes = [
        {"id": "flat", "name": "破军", "group": "g", "bonuses": {"damage": .1}},
        {"id": "hurt", "name": "血勇", "group": "g", "conditional": [{"condition": "low_hp", "bonuses": {"damage": .2}}]},
        {"id": "heal", "name": "回春", "group": "g", "bonuses": {"healing": .2}},
    ]
    state, hero, foe = combatants(affixes)
    affixes[0]["name"] = "后续改名"
    full = simulate_battle([hero], [foe], {})
    hurt = simulate_battle([hero], [foe], {"hero": 400})
    assert [(a.id, a.name, a.stat) for a in full.events[0].effects[0].affixes] == [("flat", "破军", "damage")]
    assert {a.id for a in hurt.events[0].effects[0].affixes} == {"flat", "hurt"}
    assert hurt.events[0].effects[0].amount > full.events[0].effects[0].amount
    # 来源只写入战斗副本，序列化和重建不会把上次修正再叠一次。
    restored = GameState.model_validate_json(state.model_dump_json())
    assert with_affixes(restored.active_run)[0] == hero
    assert not restored.active_run.party_snapshot.combatants[0].affix_sources


def test_sources_respect_flat_and_conditional_caps():
    affixes = [
        {"id": "flat1", "group": "g", "bonuses": {"damage": .15}},
        {"id": "flat2", "group": "g", "bonuses": {"damage": .15}},
        {"id": "c1", "group": "g", "conditional": [{"condition": "always", "bonuses": {"damage": .3}}]},
        {"id": "c2", "group": "g", "conditional": [{"condition": "always", "bonuses": {"damage": .3}}]},
        {"id": "c3", "group": "g", "conditional": [{"condition": "always", "bonuses": {"damage": .1}}]},
    ]
    _, hero, foe = combatants(affixes)
    effect = simulate_battle([hero], [foe], {}).events[0].effects[0]
    values = {a.id: a.value for a in effect.affixes}
    assert values == pytest.approx({"flat1": .15, "flat2": .05, "c1": .3, "c2": .05})


@pytest.mark.parametrize("kind,stat", [("heal", "healing"), ("shield", "shielding")])
def test_support_action_records_its_own_modifier(kind, stat):
    affixes = [{"id": "support", "name": "护持", "group": "g", "bonuses": {stat: .2, "damage": .1}}]
    _, hero, foe = combatants(affixes, [{"kind": kind, "target": "self"}])
    effect = simulate_battle([hero], [foe], {"hero": 300}).events[0].effects[0]
    assert effect.kind == kind
    assert [(a.id, a.stat, a.unit_id) for a in effect.affixes] == [("support", stat, "hero")]


def test_defender_reduction_sources_keep_owner_and_total_cap():
    affixes = [
        {"id": "flat", "group": "g", "bonuses": {"taken_damage": .2}},
        {"id": "conditional", "group": "g", "conditional": [{"condition": "low_hp", "bonuses": {"taken_damage": .15}}]},
    ]
    _, hero, foe = combatants(affixes)
    result = simulate_battle([hero], [foe], {"hero": 400})
    effect = next(e for e in result.events if e.actor_id == "foe").effects[0]
    assert {a.id: a.value for a in effect.affixes} == pytest.approx({"flat": .2, "conditional": .1})
    assert all(a.unit_id == "hero" and a.stat == "taken_damage" for a in effect.affixes)


def test_attribute_sources_are_visible_in_initial_state_and_old_events_default_empty():
    affixes = [{"id": "old", "name": "旧回春", "group": "g", "effects": [
        {"stat": "hp", "scope": "run", "mode": "add_pct", "value": .04},
    ]}]
    _, hero, foe = combatants(affixes)
    initial = simulate_battle([hero], [foe], {}).initial_units[0]
    assert initial.max_hp == 1040
    assert [(a.id, a.name, a.stat, a.value) for a in initial.affixes] == [("old", "旧回春", "hp", .04)]
    old_effect = BattleEffectResult.model_validate({"target_id": "hero", "kind": "heal", "amount": 5,
                                                  "hp_after": 10, "shield_after": 0, "source": "old"})
    assert old_effect.affixes == []
