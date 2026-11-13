"""正式敌人群体技能的多目标战报与属性变化。"""

import pytest

from app.config_loader import load_enemies
from app.domain.battle import simulate_battle
from app.models.battle import BattleUnit, SkillDefinition


def target_unit(side: str, slot: int) -> BattleUnit:
    """低速高气血陪练，确保群体技能施放时双方六人都存活。"""
    key = f"{side}:{slot}"
    return BattleUnit(
        id=key, template_id=key, name=key, slot=slot,
        health=10000, attack=10, defense=10, speed=1,
        active=SkillDefinition(id=f"{key}-active", name="普攻", type="active"),
        passive=SkillDefinition(id=f"{key}-passive", name="无被动", type="passive"),
    )


@pytest.mark.parametrize("enemy_id, target_side, stat, attribute, value", [
    ("vine_spirit", "enemy", "def", "defense", .15),
    ("lantern_wraith", "ally", "atk", "attack", -.1),
])
def test_enemy_group_buff_affects_all_six_living_targets(
    enemy_id, target_side, stat, attribute, value,
) -> None:
    """木魈给六名同伴加防，灯使给六名对手削攻，逐人留下实际状态变化。"""
    config = load_enemies()[enemy_id]
    base = config["base_stats"]
    caster = BattleUnit(
        id=f"enemy:0:{enemy_id}", template_id=enemy_id, name=config["name"], slot=0,
        health=base["hp"], attack=base["atk"], defense=base["def"], speed=base["spd"],
        active=SkillDefinition.model_validate(config["skill"]),
        passive=SkillDefinition.model_validate(config["passive"]),
    )
    allies = [target_unit("ally", slot) for slot in range(6)]
    enemies = [caster, *[target_unit("enemy", slot) for slot in range(1, 6)]]

    battle = simulate_battle(allies, enemies, {})

    opening = battle.events[0]
    assert opening.actor_id == caster.id
    assert opening.skill_id == config["skill"]["id"]
    expected = allies if target_side == "ally" else enemies
    effects = [effect for effect in opening.effects if effect.kind == "buff"]
    assert [effect.target_id for effect in effects] == [unit.id for unit in expected]
    assert all(effect.stat == stat and effect.value == pytest.approx(value) for effect in effects)
    initial = {unit.id: unit for unit in battle.initial_units}
    for unit in opening.units:
        if unit.side == target_side:
            assert getattr(unit, attribute) == pytest.approx(
                getattr(initial[unit.id], attribute) * (1 + value),
            )
            assert any(status.stat == stat and status.value == value for status in unit.statuses)
        else:
            assert not unit.statuses
