"""个人装备：确定性掉落、四槽归属、强化、洗练与熔炼。"""

from __future__ import annotations

from app.domain.facilities import GRADE_MULTIPLIERS
from app.domain.progression import is_on_run
from app.domain.rng import Pcg32
from app.models.equipment import GearAffix, GearItem, GearView
from app.models.save import DiscipleState, GameState

SLOTS = ("weapon", "armor", "boots", "ring")
LEGACY_SLOTS = {
    "qing_feng_jian": "weapon", "xuan_tie_jia": "armor",
    "liu_yun_xue": "boots", "hu_xin_jing": "ring",
    "ju_ling_pei": "ring", "po_mo_fu": "ring",
}


def equipment_stats(item: GearItem) -> dict[str, float]:
    """实例保留掉落时属性；强化只按已经存下的成长步长提高主属性。"""
    stats = dict(item.extra_stats)
    stats[item.main_stat] = stats.get(item.main_stat, 0) + item.main_value * (1 + item.level * item.growth_per_level)
    if item.affix:
        stats[item.affix] = stats.get(item.affix, 0) + item.affix_value
    return {key: round(value, 6) for key, value in stats.items()}


def combat_equipment_bonuses(state: GameState, disciple: DiscipleState) -> dict[str, float]:
    """只汇总该弟子实际穿戴的装备，不把个人效果写回宗门加成。"""
    bonuses: dict[str, float] = {}
    for slot, item_id in disciple.gear_slots.items():
        item = state.gear.get(item_id)
        if item is None or item.slot != slot:
            continue
        for stat, value in equipment_stats(item).items():
            bonuses[stat] = bonuses.get(stat, 0) + value
    return bonuses


def gear_owner(state: GameState, item_id: str) -> DiscipleState | None:
    return next((d for d in state.disciples if item_id in d.gear_slots.values()), None)


def _next_id(state: GameState) -> str:
    reserved = set(state.gear)
    if state.active_run is not None:
        reserved.update(item.id for item in state.active_run.pending_gear)
    item_id = f"gear_{state.next_gear_id}"
    state.next_gear_id += 1
    while item_id in reserved:
        item_id = f"gear_{state.next_gear_id}"
        state.next_gear_id += 1
    return item_id


def _roll_affix(rng: Pcg32, slot: str, tier: int, config: dict) -> GearAffix:
    stat = rng.pick(config["affix_pools"][slot])
    grade = rng.randint(1, len(config["affix_grades"]))
    value = config["affix_grades"][grade - 1] * (1 + (tier - 1) * config["tier_growth"])
    return GearAffix(stat=stat, grade=grade, value=round(value, 6))


def roll_drop(
    state: GameState, rng: Pcg32, tier: int, slot: str | None = None, *, config: dict,
) -> GearItem:
    """生成未入库实例；出征先保存到待结算奖励，结算时才允许穿戴或熔炼。"""
    slot = slot or rng.pick(list(SLOTS))
    definitions = [item for item in config["definitions"] if item["slot"] == slot]
    definition = definitions[rng.randint(0, len(definitions) - 1)]
    affix = _roll_affix(rng, slot, tier, config)
    item = GearItem(
        id=_next_id(state), definition_id=definition["id"], name=definition["name"],
        slot=slot, tier=tier, main_stat=definition["stat"],
        main_value=round(definition["value"] * (1 + (tier - 1) * config["tier_growth"]), 6),
        growth_per_level=config["growth_per_level"],
        affix=affix.stat, affix_grade=affix.grade, affix_value=affix.value,
    )
    return item


def grant_drop(
    state: GameState, rng: Pcg32, tier: int, slot: str | None = None, *, config: dict,
) -> GearItem:
    """无需出征结算的奖励直接入库，调用者负责与其余奖励原子落档。"""
    item = roll_drop(state, rng, tier, slot, config=config)
    state.gear[item.id] = item
    return item


def migrate_equipment(state: GameState, recipes: dict[str, dict]) -> None:
    """旧器具记录转换一次；只移除可由记录解释的器具加成，余量与旧局快照保留。"""
    if state.equipment_version >= 1:
        return
    for recipe_id in dict.fromkeys(state.crafted_recipes):
        recipe = recipes.get(recipe_id)
        if recipe_id not in LEGACY_SLOTS or recipe is None or recipe.get("kind") != "artifact":
            continue
        level = state.recipe_levels.get(recipe_id, 1)
        multiplier = GRADE_MULTIPLIERS.get(level, 1)
        stats: dict[str, float] = {}
        for effect in recipe.get("effects", []):
            if effect.get("scope") != "permanent" or effect.get("mode") != "add_pct":
                continue
            stat, value = effect["stat"], effect["value"] * multiplier
            available = max(0, state.bonuses.get(stat, 0))
            converted = min(available, value)
            if converted <= 0:
                continue
            stats[stat] = stats.get(stat, 0) + converted
            remaining = round(available - converted, 10)
            if remaining:
                state.bonuses[stat] = remaining
            else:
                state.bonuses.pop(stat, None)
        if not stats:
            continue
        main_stat = next(iter(stats))
        item = GearItem(
            id=_next_id(state), definition_id=recipe_id, name=recipe["name"],
            slot=LEGACY_SLOTS[recipe_id], tier=level, main_stat=main_stat,
            main_value=stats.pop(main_stat), extra_stats=stats, source="legacy",
            invested={key: count * sum(range(1, level + 1)) for key, count in recipe["inputs"].items()},
        )
        state.gear[item.id] = item
    state.equipment_version = 1


def equip_gear(state: GameState, item_id: str, disciple_id: str) -> str | None:
    item = state.gear.get(item_id)
    disciple = next((d for d in state.disciples if d.id == disciple_id), None)
    if item is None:
        return "装备不存在"
    if disciple is None:
        return "弟子不存在"
    owner = gear_owner(state, item_id)
    if is_on_run(state, disciple) or owner is not None and is_on_run(state, owner):
        return "出征中的弟子暂不可换装"
    if item.slot == "weapon" and disciple.equipment:
        return "请先卸下当前专武"
    if owner is disciple:
        return "已装备该物品"
    if owner is not None:
        del owner.gear_slots[item.slot]
    disciple.gear_slots[item.slot] = item_id
    return None


def unequip_gear(state: GameState, item_id: str) -> str | None:
    owner = gear_owner(state, item_id)
    if owner is None:
        return "该装备未穿戴"
    if is_on_run(state, owner):
        return "出征中的弟子暂不可换装"
    slot = next(slot for slot, value in owner.gear_slots.items() if value == item_id)
    del owner.gear_slots[slot]
    return None


def modification_reason(state: GameState, item: GearItem) -> str:
    owner = gear_owner(state, item.id)
    if owner is not None and is_on_run(state, owner):
        return "出征中的装备暂不可改动"
    return ""


def upgrade_costs(item: GearItem, config: dict) -> dict[str, int]:
    return {config["material"]: config["upgrade_base_cost"] * item.tier * (item.level + 1)}


def reforge_costs(item: GearItem, config: dict) -> dict[str, int]:
    return {config["material"]: config["reforge_base_cost"] * item.tier}


def smelt_yield(item: GearItem, config: dict) -> dict[str, int]:
    """掉落本体有固定产量；已投入资源按各项累计额回收八成并向下取整。"""
    result = {config["material"]: config["smelt_base"] * item.tier}
    for resource, count in item.invested.items():
        refund = count * 4 // 5
        if refund:
            result[resource] = result.get(resource, 0) + refund
    return result


def _can_pay(state: GameState, costs: dict[str, int]) -> bool:
    return all(state.inventory.get(resource, 0) >= count for resource, count in costs.items())


def _pay(state: GameState, costs: dict[str, int]) -> None:
    for resource, count in costs.items():
        state.inventory[resource] -= count
        if state.inventory[resource] == 0:
            del state.inventory[resource]


def upgrade_gear(state: GameState, item_id: str, config: dict) -> str | None:
    item = state.gear.get(item_id)
    if item is None:
        return "装备不存在"
    reason = modification_reason(state, item)
    if reason:
        return reason
    if item.pending_affix is not None:
        return "请先选择洗练结果"
    if item.level >= state.facility_levels.get("forge", 1) * config["levels_per_forge"]:
        return "已达当前强化上限，请先升级炼器阁"
    costs = upgrade_costs(item, config)
    if not _can_pay(state, costs):
        return "炼器精粹不足"
    _pay(state, costs)
    for resource, count in costs.items():
        item.invested[resource] = item.invested.get(resource, 0) + count
    item.level += 1
    return None


def reforge_gear(state: GameState, item_id: str, config: dict) -> str | None:
    item = state.gear.get(item_id)
    if item is None:
        return "装备不存在"
    reason = modification_reason(state, item)
    if reason:
        return reason
    if item.pending_affix is not None:
        return "请先选择本次洗练结果"
    costs = reforge_costs(item, config)
    if not _can_pay(state, costs):
        return "炼器精粹不足"
    # 独立游标不改变世界生成与出征序列；候选和扣费在同一命令中保存。
    rng = Pcg32(state.rng_seed)
    rng.advance_to(state.gear_rng_cursor)
    roll = _roll_affix(rng, item.slot, item.tier, config)
    _pay(state, costs)
    state.gear_rng_cursor = rng.cursor
    item.pending_affix = roll
    return None


def resolve_reforge(state: GameState, item_id: str, keep: bool) -> str | None:
    item = state.gear.get(item_id)
    if item is None:
        return "装备不存在"
    reason = modification_reason(state, item)
    if reason:
        return reason
    if item.pending_affix is None:
        return "没有待选择的洗练结果"
    if not keep:
        item.affix = item.pending_affix.stat
        item.affix_grade = item.pending_affix.grade
        item.affix_value = item.pending_affix.value
    item.pending_affix = None
    return None


def smelt_gear(state: GameState, item_id: str, config: dict) -> str | None:
    item = state.gear.get(item_id)
    if item is None:
        return "装备不存在或为不可熔炼的专武"
    if gear_owner(state, item_id) is not None:
        return "请先卸下装备再熔炼"
    if item.locked:
        return "请先解除装备锁定"
    if item.pending_affix is not None:
        return "请先选择洗练结果"
    for resource, count in smelt_yield(item, config).items():
        state.inventory[resource] = state.inventory.get(resource, 0) + count
    del state.gear[item_id]
    return None


def gear_views(state: GameState, config: dict) -> list[GearView]:
    views: list[GearView] = []
    maximum = state.facility_levels.get("forge", 1) * config["levels_per_forge"]
    for item in state.gear.values():
        owner = gear_owner(state, item.id)
        blocked = modification_reason(state, item)
        pending = "请先选择洗练结果" if item.pending_affix is not None else ""
        costs = upgrade_costs(item, config)
        upgrade_reason = blocked or pending or ("已达当前强化上限" if item.level >= maximum else "")
        if not upgrade_reason and not _can_pay(state, costs):
            upgrade_reason = "炼器精粹不足"
        reforge = reforge_costs(item, config)
        reforge_reason = blocked or pending or ("炼器精粹不足" if not _can_pay(state, reforge) else "")
        smelt_reason = "请先卸下装备" if owner else "请先解除锁定" if item.locked else pending
        upgraded = item.model_copy(update={"level": item.level + 1})
        views.append(GearView(
            **item.model_dump(), stats=equipment_stats(item), equipped_by=owner.id if owner else None,
            max_level=maximum, equip_reason=blocked,
            unequip_reason=blocked if owner else "该装备未穿戴",
            upgrade_costs=costs, upgrade_stats=equipment_stats(upgraded), upgradeable=not upgrade_reason,
            upgrade_reason=upgrade_reason, reforge_costs=reforge, reforge_reason=reforge_reason,
            resolve_reason=blocked or ("没有待选择的洗练结果" if item.pending_affix is None else ""),
            smelt_returns=smelt_yield(item, config), smelt_reason=smelt_reason,
        ))
    return views
