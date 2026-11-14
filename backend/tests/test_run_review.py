"""复盘只汇总本场真实行动，区分我方保护与敌方保护。"""

from app.domain.run_engine import build_battle_review
from app.models.battle import BattleEffectResult, BattleEvent, BattleUnitState
from app.models.save import BattleSummary, RunNode


def unit(key, side, hp, slot=0):
    return BattleUnitState(
        id=key, template_id=key, name=key, side=side, slot=slot,
        hp=hp, max_hp=100, attack=10, defense=5, speed=10,
    )


def effect(target, kind, amount, *, hp=100, absorbed=0):
    return BattleEffectResult(
        target_id=target, kind=kind, amount=amount, absorbed=absorbed,
        hp_after=hp, shield_after=0, source="test",
    )


def summary(*, events=None, initial=None, final=None, won=False, reason="defeated"):
    return BattleSummary(
        id="review-test", node=RunNode(kind="battle", enemy="battle_0", power=50),
        party_power=70, enemy_power=50, hp_before=100, hp_after=40,
        damage=70, healed=10, won=won, rounds=2, reason=reason,
        events=events or [], initial_units=initial or [], final_units=final or [],
    )


def test_review_counts_only_ally_shields_and_uses_actual_effect_amounts():
    ally, enemy = unit("ally", "ally", 100), unit("enemy", "enemy", 100)
    event = BattleEvent(
        sequence=1, round=1, actor_id="ally", skill_id="test", skill_name="测试招式", vfx="shield",
        units=[ally, enemy], effects=[
            effect("ally", "shield", 12), effect("enemy", "shield", 90),
            effect("ally", "damage", 5, absorbed=7), effect("enemy", "damage", 30, absorbed=80),
        ],
    )
    review = build_battle_review(summary(events=[event], initial=[ally, enemy], final=[ally, enemy]))
    assert review.shield_applied == 12
    assert review.shield_absorbed == 7
    assert review.healed == 10
    assert review.first_down_id is None


def test_review_ignores_members_down_at_start_and_limits_key_actions():
    initial = [unit("already_down", "ally", 0), unit("new_down", "ally", 20, 1), unit("enemy", "enemy", 100)]
    first = [initial[0], unit("new_down", "ally", 0, 1), initial[2]]
    events = [
        BattleEvent(
            sequence=1, round=1, actor_id="enemy", skill_id="first", skill_name="首击", vfx="strike",
            units=first, effects=[effect("new_down", "damage", 20, hp=0)],
        ),
        BattleEvent(
            sequence=2, round=2, actor_id="enemy", skill_id="second", skill_name="后击", vfx="strike",
            units=first, effects=[
                effect("z", "damage", 30), effect("a", "damage", 30), effect("b", "damage", 30),
                effect("zero", "damage", 0),
            ],
        ),
    ]
    review = build_battle_review(summary(events=events, initial=initial, final=first))
    assert review.first_down_id == review.first_down_name == "new_down"
    assert [item["target_id"] for item in review.key_actions] == ["a", "b", "z"]
    assert [item["sequence"] for item in review.key_actions] == [2, 2, 2]
    assert [enemy.id for enemy in review.surviving_enemies] == ["enemy"]


def test_review_same_damage_uses_earlier_action_first():
    ally, enemy = unit("ally", "ally", 100), unit("enemy", "enemy", 100)
    events = [BattleEvent(
        sequence=sequence, round=sequence, actor_id="ally", skill_id="hit", skill_name="攻击", vfx="strike",
        effects=[effect("enemy", "damage", 10)], units=[ally, enemy],
    ) for sequence in range(1, 5)]
    review = build_battle_review(summary(events=events, initial=[ally, enemy], final=[ally, enemy], reason="round_limit"))
    assert [item["sequence"] for item in review.key_actions] == [1, 2, 3]
    assert review.reason == "round_limit" and review.hp_after == 40
    assert review.first_down_id is None
    assert review.shield_applied == review.shield_absorbed == 0


def test_review_missing_events_does_not_invent_protection_statistics():
    review = build_battle_review(summary())
    assert review.first_down_id is None and review.key_actions == []
    assert review.shield_applied is None and review.shield_absorbed is None
