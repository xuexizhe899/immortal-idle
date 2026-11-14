"""培养预览：复用战斗属性、升级费用与值守速率，不扣资源、不写存档。

预览只读；真正的升级/突破仍由 progression 的命令函数执行。
"""

from __future__ import annotations

from app.domain.duty import personal_duty_rates
from app.domain.progression import (
    LEVEL_CAPS, MAX_REALM, breakthrough_cost, is_on_run, level_cap, upgrade_cost,
)
from app.domain.run_engine import combatant
from app.domain.weapons import combat_bonuses
from app.models.api import TrainingPreview, TrainingStats, TrainingStep
from app.models.save import DiscipleState, GameState


def stats_for(
    disciple: DiscipleState, template: dict, skills: dict[str, dict],
    bonuses: dict[str, float], weapons: dict[str, dict], slot: int = 0,
    weapon_levels: dict[str, int] | None = None, training_level: int = 1,
) -> TrainingStats:
    """等级、境界、伤势、个人/宗门加成与已装备专武后的当前属性。"""
    unit = combatant(
        disciple, template, skills,
        combat_bonuses(disciple, bonuses, weapons, weapon_levels), slot,
    )
    rates = personal_duty_rates(disciple, template, training_level)
    return TrainingStats(
        level=disciple.level, realm=disciple.realm,
        health=unit.health, attack=round(unit.attack, 2),
        defense=round(unit.defense, 2), speed=round(unit.speed, 2),
        duty_rates={key: round(value, 4) for key, value in rates.items()},
    )


def preview(
    state: GameState, disciple: DiscipleState, template: dict, skills: dict[str, dict],
    weapons: dict[str, dict],
) -> TrainingPreview:
    """生成当前/下一等级的只读预览，包含限制原因与旧档超限标记。"""
    cap = level_cap(disciple.realm)
    slot = next(
        (index for index, item in enumerate(state.disciples) if item.id == disciple.id), 0,
    )
    training_level = state.facility_levels.get("training", 1)
    current = stats_for(disciple, template, skills, state.bonuses, weapons, slot, state.weapon_levels, training_level)

    if disciple.level >= cap:
        next_level = TrainingStep(
            kind="level", allowed=False,
            reason=f"已达境界 {disciple.realm} 的等级上限 {cap}，请先突破",
        )
    else:
        costs = upgrade_cost(disciple)
        reason = ""
        if is_on_run(state, disciple):
            reason = "出征中的弟子暂不可培养"
        elif any(getattr(state.resources, key) < amount for key, amount in costs.items()):
            reason = "修为或灵石不足"
        next_level = TrainingStep(
            kind="level", allowed=not reason, reason=reason, costs=costs,
            target=stats_for(
                disciple.model_copy(update={"level": disciple.level + 1}),
                template, skills, state.bonuses, weapons, slot, state.weapon_levels, training_level,
            ),
        )

    if disciple.realm >= MAX_REALM:
        next_realm = TrainingStep(
            kind="realm", allowed=False, reason="已达当前最高境界",
        )
    else:
        required = LEVEL_CAPS.get(disciple.realm)
        if required is None:
            next_realm = TrainingStep(
                kind="realm", allowed=False, reason="当前境界不支持继续突破",
            )
        else:
            costs = breakthrough_cost(disciple, template)
            reason = ""
            if is_on_run(state, disciple):
                reason = "出征中的弟子暂不可突破"
            elif disciple.level < required:
                reason = f"需要达到 {required} 级才能突破至境界 {disciple.realm + 1}"
            elif state.resources.reputation < costs.get("reputation", 0.0):
                reason = f"声望不足（需要 {costs.get('reputation', 0.0):g}）"
            next_realm = TrainingStep(
                kind="realm", allowed=not reason, reason=reason, costs=costs,
                requires_level=required, alternative_recipe_id="po_jing_dan",
                target=stats_for(
                    disciple.model_copy(update={"realm": disciple.realm + 1}),
                    template, skills, state.bonuses, weapons, slot, state.weapon_levels, training_level,
                ),
            )

    return TrainingPreview(
        disciple_id=disciple.id, level=disciple.level, realm=disciple.realm,
        level_cap=cap, max_realm=MAX_REALM,
        legacy_over_cap=disciple.level > cap or disciple.realm > MAX_REALM,
        current=current, next_level=next_level, next_realm=next_realm,
    )
