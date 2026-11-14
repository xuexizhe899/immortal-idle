"""专属武器：唯一归属、单槽装备与个人属性加成。

武器定义保存属性、材料与升级专材；存档分别记录唯一武器归属及等级。
出发时由战斗快照固化最终数值，之后换装或改配置不影响进行中的出征。
"""

from __future__ import annotations

from app.domain.progression import is_on_run
from app.domain.facilities import GRADE_MULTIPLIERS
from app.models.api import WeaponView
from app.models.save import DiscipleState, GameState

COMBAT_STATS = {"hp", "atk", "def", "spd"}
BATTLE_STATS = {"damage", "healing", "shielding"}


def equipped_weapon(
    disciple: DiscipleState, weapons: dict[str, dict], weapon_levels: dict[str, int] | None = None,
) -> dict | None:
    """返回已识别且生效的专武；旧档未知 ID 保留但不提供加成。"""
    for weapon_id in disciple.equipment:
        if weapon_id in weapons:
            weapon = weapons[weapon_id]
            multiplier = GRADE_MULTIPLIERS[(weapon_levels or {}).get(weapon_id, 1)]
            return {**weapon, "stats": {stat: value * multiplier for stat, value in weapon["stats"].items()}}
    return None


def weapon_owner(state: GameState, weapon_id: str) -> DiscipleState | None:
    """正在装备该武器的弟子；同一把唯一武器最多一人。"""
    return next((d for d in state.disciples if weapon_id in d.equipment), None)


def owned_weapon(state: GameState, weapon_id: str) -> bool:
    """行囊或已装备都算已拥有，阻止重复锻造。"""
    return state.inventory.get(weapon_id, 0) > 0 or weapon_owner(state, weapon_id) is not None


def weapon_reason(
    state: GameState, weapon: dict, templates: dict[str, dict],
    materials: dict[str, dict],
) -> str:
    """返回不能锻造的具体原因；空字符串表示可锻造。"""
    weapon_id = weapon["id"]
    if owned_weapon(state, weapon_id):
        return "已拥有该专武"

    template_id = weapon["template_id"]
    disciple = next((d for d in state.disciples if d.template_id == template_id), None)
    if disciple is None:
        return "尚未拥有该弟子"

    unlock = weapon["unlock"]
    if state.tower_floor < unlock["floor"]:
        return f"问道塔需达到 {unlock['floor']} 层"
    if disciple.level < unlock["level"]:
        return f"弟子需达到 {unlock['level']} 级"

    missing = [
        f"{materials.get(material_id, {}).get('name', material_id)} "
        f"{count - state.inventory.get(material_id, 0)}"
        for material_id, count in weapon["inputs"].items()
        if state.inventory.get(material_id, 0) < count
    ]
    return f"材料不足：{'、'.join(missing)}" if missing else ""


def craft_weapon(
    state: GameState, weapon_id: str, weapons: dict[str, dict],
    templates: dict[str, dict], materials: dict[str, dict],
) -> str | None:
    """锻造一把专武入行囊；成功返回 None，失败不扣材料。"""
    if state.active_run is not None:
        return "请先完成当前出征再锻造"
    weapon = weapons.get(weapon_id)
    if weapon is None:
        return "专武不存在"
    error = weapon_reason(state, weapon, templates, materials)
    if error:
        return error

    for material_id, count in weapon["inputs"].items():
        state.inventory[material_id] -= count
        if state.inventory[material_id] <= 0:
            del state.inventory[material_id]
    state.inventory[weapon_id] = state.inventory.get(weapon_id, 0) + 1
    state.weapon_levels[weapon_id] = 1
    return None


def equip_weapon(
    state: GameState, weapon_id: str, disciple_id: str, weapons: dict[str, dict],
) -> str | None:
    """把行囊中的专武装备给对应弟子；单槽，失败不改变状态。"""
    weapon = weapons.get(weapon_id)
    if weapon is None:
        return "专武不存在"
    disciple = next((d for d in state.disciples if d.id == disciple_id), None)
    if disciple is None:
        return "弟子不存在"
    if weapon["template_id"] != disciple.template_id:
        return "该专武不属于这名弟子"
    if is_on_run(state, disciple):
        return "出征中的弟子暂不可换装"
    if state.inventory.get(weapon_id, 0) < 1:
        return "行囊中没有该专武"
    if weapon_id in disciple.equipment:
        return "已装备该专武"
    if disciple.equipment:
        return "请先卸下当前专武"

    remaining = state.inventory[weapon_id] - 1
    if remaining:
        state.inventory[weapon_id] = remaining
    else:
        del state.inventory[weapon_id]
    disciple.equipment = [weapon_id]
    return None


def unequip_weapon(
    state: GameState, disciple_id: str, weapons: dict[str, dict],
) -> str | None:
    """卸下专武放回行囊；未知旧装备保留，不擅自删除。"""
    disciple = next((d for d in state.disciples if d.id == disciple_id), None)
    if disciple is None:
        return "弟子不存在"
    if is_on_run(state, disciple):
        return "出征中的弟子暂不可换装"
    if not disciple.equipment:
        return "该弟子未装备专武"
    if any(weapon_id not in weapons for weapon_id in disciple.equipment):
        return "旧装备无法识别，暂不可卸下"

    for weapon_id in disciple.equipment:
        state.inventory[weapon_id] = state.inventory.get(weapon_id, 0) + 1
    disciple.equipment = []
    return None


def combat_bonuses(
    disciple: DiscipleState, permanent: dict[str, float], weapons: dict[str, dict],
    weapon_levels: dict[str, int] | None = None,
) -> dict[str, float]:
    """宗门永久加成、个人丹药与专武的基础属性合并成加区小数。"""
    merged = dict(permanent)
    for stat, value in disciple.bonuses.items():
        merged[stat] = merged.get(stat, 0.0) + value
    weapon = equipped_weapon(disciple, weapons, weapon_levels)
    if weapon is not None:
        for stat, value in weapon["stats"].items():
            if stat in COMBAT_STATS:
                merged[stat] = merged.get(stat, 0.0) + value
    return merged


def battle_bonuses(
    disciple: DiscipleState, weapons: dict[str, dict], weapon_levels: dict[str, int] | None = None,
) -> dict[str, float]:
    """专武提供的伤害、治疗、护盾乘区加成。"""
    weapon = equipped_weapon(disciple, weapons, weapon_levels)
    if weapon is None:
        return {}
    return {
        stat: value for stat, value in weapon["stats"].items()
        if stat in BATTLE_STATS
    }


def weapon_upgrade(state: GameState, weapon: dict) -> dict:
    """同一把专武逐级提升；费用和可用性供预览与命令共用。"""
    weapon_id = weapon["id"]
    level = state.weapon_levels.get(weapon_id, 1) if owned_weapon(state, weapon_id) else 0
    target = min(level + 1, 3)
    inputs = {key: count * target for key, count in weapon["inputs"].items()}
    if level:
        material = weapon.get("upgrade_material", "gong_fa_qi_pei" if "damage" in weapon["stats"] else "hu_chi_qi_pei")
        inputs[material] = inputs.get(material, 0) + target - 1
    reason = ""
    if not level:
        reason = "请先锻造该专武"
    elif state.active_run is not None:
        reason = "请先完成当前出征再升级专武"
    elif level >= 3:
        reason = "专武已达最高等级"
    elif target > state.facility_levels.get("forge", 1):
        reason = "请先升级炼器炉"
    elif any(state.inventory.get(key, 0) < count for key, count in inputs.items()):
        reason = "升级材料不足"
    return {
        "level": level, "max_level": state.facility_levels.get("forge", 1),
        "upgrade_inputs": inputs if level < 3 else {},
        "upgrade_stats": {key: value * GRADE_MULTIPLIERS[target] for key, value in weapon["stats"].items()},
        "upgradeable": not reason, "upgrade_reason": reason,
    }


def upgrade_weapon(state: GameState, weapon_id: str, weapons: dict[str, dict]) -> str | None:
    weapon = weapons.get(weapon_id)
    if weapon is None:
        return "专武不存在"
    preview = weapon_upgrade(state, weapon)
    if preview["upgrade_reason"]:
        return preview["upgrade_reason"]
    for material_id, count in preview["upgrade_inputs"].items():
        remaining = state.inventory[material_id] - count
        if remaining:
            state.inventory[material_id] = remaining
        else:
            del state.inventory[material_id]
    # 等级属于这把唯一专武，装备与卸下不会重置或重复发放增益。
    state.weapon_levels[weapon_id] = preview["level"] + 1
    return None


def weapon_views(
    state: GameState, weapons: dict[str, dict], templates: dict[str, dict],
    materials: dict[str, dict],
) -> list[WeaponView]:
    """生成专武列表：静态定义 + 当前归属 + 服务端校验后的可锻造原因。"""
    views: list[WeaponView] = []
    for weapon_id in sorted(weapons):
        weapon = weapons[weapon_id]
        owner = weapon_owner(state, weapon_id)
        in_inventory = state.inventory.get(weapon_id, 0) > 0
        reason = weapon_reason(state, weapon, templates, materials)
        views.append(WeaponView(
            id=weapon_id,
            name=weapon["name"],
            template_id=weapon["template_id"],
            template_name=templates.get(weapon["template_id"], {}).get(
                "name", weapon["template_id"],
            ),
            stats={key: value * GRADE_MULTIPLIERS[state.weapon_levels.get(weapon_id, 1)] for key, value in weapon["stats"].items()},
            inputs=weapon["inputs"],
            unlock_floor=weapon["unlock"]["floor"],
            unlock_level=weapon["unlock"]["level"],
            owned=in_inventory or owner is not None,
            in_inventory=in_inventory,
            equipped_by=owner.id if owner else None,
            reason=reason,
            craftable=not reason,
            **weapon_upgrade(state, weapon),
        ))
    return views
