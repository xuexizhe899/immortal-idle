"""专属武器：唯一归属、单槽装备与个人属性加成。

武器定义只保存属性与材料；状态里只记录行囊数量或弟子已装备的武器 ID。
出发时由战斗快照固化最终数值，之后换装或改配置不影响进行中的出征。
"""

from __future__ import annotations

from app.domain.progression import is_on_run
from app.models.api import WeaponView
from app.models.save import DiscipleState, GameState

COMBAT_STATS = {"hp", "atk", "def", "spd"}
BATTLE_STATS = {"damage", "healing", "shielding"}


def equipped_weapon(disciple: DiscipleState, weapons: dict[str, dict]) -> dict | None:
    """返回已识别且生效的专武；旧档未知 ID 保留但不提供加成。"""
    for weapon_id in disciple.equipment:
        if weapon_id in weapons:
            return weapons[weapon_id]
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
) -> dict[str, float]:
    """宗门永久加成、个人丹药与专武的基础属性合并成加区小数。"""
    merged = dict(permanent)
    for stat, value in disciple.bonuses.items():
        merged[stat] = merged.get(stat, 0.0) + value
    weapon = equipped_weapon(disciple, weapons)
    if weapon is not None:
        for stat, value in weapon["stats"].items():
            if stat in COMBAT_STATS:
                merged[stat] = merged.get(stat, 0.0) + value
    return merged


def battle_bonuses(disciple: DiscipleState, weapons: dict[str, dict]) -> dict[str, float]:
    """专武提供的伤害、治疗、护盾乘区加成。"""
    weapon = equipped_weapon(disciple, weapons)
    if weapon is None:
        return {}
    return {
        stat: value for stat, value in weapon["stats"].items()
        if stat in BATTLE_STATS
    }


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
            stats=weapon["stats"],
            inputs=weapon["inputs"],
            unlock_floor=weapon["unlock"]["floor"],
            unlock_level=weapon["unlock"]["level"],
            owned=in_inventory or owner is not None,
            in_inventory=in_inventory,
            equipped_by=owner.id if owner else None,
            reason=reason,
            craftable=not reason,
        ))
    return views
