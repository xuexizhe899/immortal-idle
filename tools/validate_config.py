#!/usr/bin/env python3
"""配置校验：结构 + 跨文件引用完整性。

用法：
    python tools/validate_config.py

退出码 1 表示有错误，每条错误都带文件路径与字段名。只用标准库，保证 CI 裸 Python 可跑。
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
ASSETS_DIR = ROOT / "frontend" / "public" / "assets"

ORIGINS = {"sanguo", "myth", "history"}
LEANS = {"attack", "defense", "support", "craft"}
RARITIES = {1, 2, 3}
SKILL_TYPES = {"active", "passive"}
EFFECT_MODES = {"add", "add_pct", "mul_pct"}
EFFECT_SCOPES = {"battle", "run", "duty", "permanent"}
COMBAT_STATS = {"hp", "atk", "def", "spd"}
YIELD_STATS = {
    "cultivation_rate",
    "spirit_stone_rate",
    "stamina_rate",
    "material_rate",
    "injury_rate",
}
STATS = COMBAT_STATS | YIELD_STATS
RECIPE_KINDS = {"pill", "artifact"}
CITY_PANELS = {"codex", "sect", "expedition", "tower", "duty", "forge", "alchemy"}
ACTION_KINDS = {"damage", "heal", "shield", "buff"}
ACTION_TARGETS = {"enemy_first", "enemy_lowest", "all_enemies", "ally_lowest", "all_allies", "self", "ally_template"}
CONDITIONS = {"always", "shielded", "target_weakened", "target_wounded", "low_hp", "first_round"}
AFFIX_TYPES = {"attr", "flat", "cond", "mixed"}
AFFIX_BONUS_KEYS = {"damage", "healing", "shielding", "taken_damage"}
PASSIVE_STATS = COMBAT_STATS | {"damage", "healing", "shielding"}
WEAPON_STATS = COMBAT_STATS | {"damage", "healing", "shielding"}


def is_number(value: object) -> bool:
    """判断是否为数字，排除 bool（bool 是 int 的子类，会被误判）。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_finite_number(value: object) -> bool:
    """JSON 解码器允许 NaN/Infinity，坐标不得接受这类值。"""
    return is_number(value) and (isinstance(value, int) or math.isfinite(value))


def check_city_asset(value: object, where: str, assets_dir: Path, errors: list[str]) -> None:
    """主城资产必须是 public/assets 内可落盘验证的本地路径。"""
    if (
        not isinstance(value, str) or not value.startswith("/assets/")
        or any(char in value for char in ("\\", "?", "#"))
    ):
        errors.append(f"{where}: 必须是 /assets/ 开头的本地资产路径")
        return
    asset_root = assets_dir.resolve()
    target = (asset_root / value.removeprefix("/assets/")).resolve()
    if not target.is_relative_to(asset_root):
        errors.append(f"{where}: 资产路径不得越出 frontend/public/assets")
    elif not target.is_file():
        errors.append(f"{where}: 本地资产不存在 '{value}'")


def check_city(config_dir: Path, assets_dir: Path, errors: list[str]) -> None:
    """主城可选；存在时校验真实图片和可点击区域，避免 CI 漏掉错图/错热区。"""
    path = config_dir / "ui" / "city.json"
    if not path.exists():
        return
    where = "config/ui/city.json"
    try:
        city = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError, OSError) as exc:
        errors.append(f"{where}: JSON 读取失败 - {exc}")
        return
    if not isinstance(city, dict):
        errors.append(f"{where}: 顶层必须是对象")
        return
    check_city_asset(city.get("background"), f"{where}: background", assets_dir, errors)
    aspect = city.get("aspect")
    if not is_finite_number(aspect) or aspect <= 0:
        errors.append(f"{where}: aspect 必须是有限正数")
    hotspots = city.get("hotspots")
    if not isinstance(hotspots, list) or not hotspots:
        errors.append(f"{where}: hotspots 必须是非空数组")
        return
    seen: set[str] = set()
    for index, hotspot in enumerate(hotspots):
        pos = f"{where}: hotspots[{index}]"
        if not isinstance(hotspot, dict):
            errors.append(f"{pos}: 必须是对象")
            continue
        hotspot_id = hotspot.get("id")
        if not isinstance(hotspot_id, str) or not hotspot_id.strip():
            errors.append(f"{pos}: id 必须是非空字符串")
        elif hotspot_id in seen:
            errors.append(f"{pos}: id '{hotspot_id}' 重复")
        else:
            seen.add(hotspot_id)
        panel = hotspot.get("panel")
        if not isinstance(panel, str) or panel not in CITY_PANELS:
            errors.append(f"{pos}: panel 必须是七个已知入口之一 {sorted(CITY_PANELS)}")
        if hotspot.get("sprite") is not None:
            check_city_asset(hotspot["sprite"], f"{pos}.sprite", assets_dir, errors)
        valid_coordinates = True
        for key in ("x", "y", "w", "h"):
            value = hotspot.get(key)
            valid = is_finite_number(value) and (
                0 <= value <= 100 if key in ("x", "y") else 0 < value <= 100
            )
            if not valid:
                errors.append(f"{pos}.{key}: 必须是有效的有限百分比（中心 0..100，尺寸 >0..100）")
                valid_coordinates = False
        if valid_coordinates:
            x, y, width, height = (hotspot[key] for key in ("x", "y", "w", "h"))
            if not (
                width / 2 <= x <= 100 - width / 2
                and height / 2 <= y <= 100 - height / 2
            ):
                errors.append(f"{pos}: 热区边界必须完整位于 0..100 的主城范围内")


def load_collection(config_dir: Path, name: str, errors: list[str]) -> dict[str, dict]:
    """读取 config/<name> 下所有 JSON，按 id 建索引，并检查 id 与文件名一致。"""
    folder = config_dir / name
    index: dict[str, dict] = {}
    if not folder.is_dir():
        return index

    for path in sorted(folder.glob("*.json")):
        where = f"config/{name}/{path.name}"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{where}: JSON 解析失败 - {exc}")
            continue
        if not isinstance(data, dict):
            errors.append(f"{where}: 顶层必须是对象")
            continue

        item_id = data.get("id")
        if not isinstance(item_id, str) or not item_id:
            errors.append(f"{where}: 缺少非空字符串字段 'id'")
            continue
        if item_id != path.stem:
            errors.append(f"{where}: id '{item_id}' 必须与文件名 '{path.stem}' 一致")
        if item_id in index:
            errors.append(f"{where}: id '{item_id}' 重复")
            continue
        index[item_id] = data
    return index


def load_pending(config_dir: Path) -> set[str]:
    """读取待生成资产清单；文件不存在时视为空。"""
    path = config_dir / "assets_pending.json"
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")))


def check_effects(container: dict, where: str, errors: list[str]) -> None:
    """校验 effects 数组，逐个检查 stat / mode / scope / value。"""
    effects = container.get("effects", [])
    if not isinstance(effects, list):
        errors.append(f"{where}: effects 必须是数组")
        return

    for i, effect in enumerate(effects):
        pos = f"{where}: effects[{i}]"
        if not isinstance(effect, dict):
            errors.append(f"{pos}: 必须是对象")
            continue
        if effect.get("stat") not in STATS:
            errors.append(f"{pos}: 未知 stat '{effect.get('stat')}'")
        if effect.get("mode") not in EFFECT_MODES:
            errors.append(
                f"{pos}: mode '{effect.get('mode')}' 不在 {sorted(EFFECT_MODES)}"
            )
        if effect.get("scope") not in EFFECT_SCOPES:
            errors.append(
                f"{pos}: scope '{effect.get('scope')}' 不在 {sorted(EFFECT_SCOPES)}"
            )
        if not is_finite_number(effect.get("value")):
            errors.append(f"{pos}: value 必须是有限数字")


def check_integer(value: object, low: int, high: int, where: str, errors: list[str]) -> None:
    """对执行次数与持续时间设置上限，避免配置制造无限行动。"""
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        errors.append(f"{where}: 必须是 {low}..{high} 的整数")


def check_actions(actions: object, where: str, errors: list[str], *, minimum: int = 1, maximum: int = 4) -> None:
    """只接受战斗引擎实际执行的四类动作及确定性选取目标。"""
    if not isinstance(actions, list) or not minimum <= len(actions) <= maximum:
        errors.append(f"{where}: 需要 {minimum}..{maximum} 条动作")
        return
    for index, action in enumerate(actions):
        pos = f"{where}[{index}]"
        if not isinstance(action, dict):
            errors.append(f"{pos}: 必须是对象")
            continue
        unknown = set(action) - {"kind", "target", "count", "coefficient", "duration", "stat", "value", "target_template"}
        if unknown:
            errors.append(f"{pos}: 未实现的动作字段 {sorted(unknown)}")
        kind = action.get("kind")
        if not isinstance(kind, str) or kind not in ACTION_KINDS:
            errors.append(f"{pos}: kind 必须是 damage/heal/shield/buff")
        target = action.get("target")
        if not isinstance(target, str) or target not in ACTION_TARGETS:
            errors.append(f"{pos}: 未知 target '{target}'")
        if target == "ally_template" and not isinstance(action.get("target_template"), str):
            errors.append(f"{pos}: ally_template 需要 target_template")
        check_integer(action.get("count", 1), 1, 6, f"{pos}.count", errors)
        check_integer(action.get("duration", 2), 1, 20, f"{pos}.duration", errors)
        coefficient = action.get("coefficient", 1)
        if not is_finite_number(coefficient) or not 0 <= coefficient <= 10:
            errors.append(f"{pos}.coefficient: 必须是 0..10 的有限数字")
        if kind == "buff":
            if not isinstance(action.get("stat"), str) or action.get("stat") not in {"atk", "def", "spd"}:
                errors.append(f"{pos}.stat: 增减益只接受 atk/def/spd")
            value = action.get("value")
            if not is_finite_number(value) or not -.5 <= value <= 1 or value == 0:
                errors.append(f"{pos}.value: 必须是 -0.5..1 的有限非零数字")
        elif isinstance(kind, str) and kind in {"damage", "heal", "shield"} and coefficient == 0:
            errors.append(f"{pos}.coefficient: 伤害、治疗与护盾系数必须大于 0")


def check_skill(skill: dict, where: str, errors: list[str]) -> None:
    """技能仅用 actions/bonuses 执行，禁止旧 effects 与新机制并存造成双算。"""
    if not isinstance(skill.get("name"), str):
        errors.append(f"{where}: 缺少字符串字段 'name'")
    if skill.get("type") not in SKILL_TYPES:
        errors.append(f"{where}: type '{skill.get('type')}' 不在 {sorted(SKILL_TYPES)}")
    check_effects(skill, where, errors)
    if skill.get("effects"):
        errors.append(f"{where}: 可执行技能的 effects 必须为空，主动使用 actions，被动使用 bonuses")
    if skill.get("type") == "active":
        check_integer(skill.get("cooldown"), 1, 20, f"{where}.cooldown", errors)
        check_actions(skill.get("actions"), f"{where}.actions", errors)
        if not isinstance(skill.get("vfx"), str) or not skill["vfx"].strip():
            errors.append(f"{where}.vfx: 必须是非空字符串")
        if skill.get("bonuses"):
            errors.append(f"{where}: 主动招式不能携带被动 bonuses")
    elif skill.get("type") == "passive":
        bonuses = skill.get("bonuses")
        if not isinstance(bonuses, dict) or not bonuses:
            errors.append(f"{where}.bonuses: 必须是非空对象")
        else:
            for stat, value in bonuses.items():
                if stat not in PASSIVE_STATS:
                    errors.append(f"{where}.bonuses: 未实现的属性 '{stat}'")
                if not is_finite_number(value) or not 0 <= value <= 1:
                    errors.append(f"{where}.bonuses.{stat}: 必须是 0..1 的有限数字")
        if not isinstance(skill.get("condition"), str) or skill.get("condition") not in CONDITIONS:
            errors.append(f"{where}.condition: 必须是 {sorted(CONDITIONS)}")
        elif skill["condition"] != "always" and isinstance(bonuses, dict) and COMBAT_STATS & bonuses.keys():
            errors.append(f"{where}.bonuses: 条件被动只支持 damage/healing/shielding，atk/def/hp/spd 必须使用 always")
        if skill.get("actions"):
            errors.append(f"{where}: 被动不能新增行动或连锁触发")


def check_modifiers(modifiers: object, where: str, skills: dict[str, dict], errors: list[str]) -> None:
    """羁绊只修改一次技能，不引入追击事件或递归触发。"""
    if not isinstance(modifiers, list) or not 1 <= len(modifiers) <= 4:
        errors.append(f"{where}: 需要 1..4 条技能修饰")
        return
    for index, modifier in enumerate(modifiers):
        pos = f"{where}[{index}]"
        if not isinstance(modifier, dict):
            errors.append(f"{pos}: 必须是对象")
            continue
        unknown = set(modifier) - {"skill", "condition", "add_targets", "coefficient_bonus", "duration_bonus", "extra_actions"}
        if unknown:
            errors.append(f"{pos}: 未实现的技能修饰字段 {sorted(unknown)}")
        skill_id = modifier.get("skill")
        if not isinstance(skill_id, str) or skill_id not in skills or skills[skill_id].get("type") != "active":
            errors.append(f"{pos}.skill: 必须引用已存在的主动技能")
        if not isinstance(modifier.get("condition", "always"), str) or modifier.get("condition", "always") not in CONDITIONS:
            errors.append(f"{pos}.condition: 未实现的条件")
        check_integer(modifier.get("add_targets", 0), 0, 5, f"{pos}.add_targets", errors)
        check_integer(modifier.get("duration_bonus", 0), 0, 5, f"{pos}.duration_bonus", errors)
        bonus = modifier.get("coefficient_bonus", 0)
        if not is_finite_number(bonus) or not 0 <= bonus <= 1:
            errors.append(f"{pos}.coefficient_bonus: 必须是 0..1 的有限数字")
        check_actions(modifier.get("extra_actions", []), f"{pos}.extra_actions", errors, minimum=0, maximum=3)


def validate(
    config_dir: Path | None = None, assets_dir: Path | None = None
) -> list[str]:
    """执行全部校验并返回错误列表，空列表表示通过。"""
    config_dir = config_dir or CONFIG_DIR
    assets_dir = assets_dir or ASSETS_DIR
    errors: list[str] = []
    pending = load_pending(config_dir)
    check_city(config_dir, assets_dir, errors)

    skills = load_collection(config_dir, "skills", errors)
    disciples = load_collection(config_dir, "disciples", errors)
    bonds = load_collection(config_dir, "bonds", errors)
    materials = load_collection(config_dir, "materials", errors)
    recipes = load_collection(config_dir, "recipes", errors)
    weapons = load_collection(config_dir, "weapons", errors)
    affixes = load_collection(config_dir, "affixes", errors)
    enemies = load_collection(config_dir, "enemies", errors)
    events = load_collection(config_dir, "events", errors)
    modes = load_collection(config_dir, "modes", errors)

    for skill_id, skill in skills.items():
        where = f"config/skills/{skill_id}.json"
        check_skill(skill, where, errors)
        for action in skill.get("actions", []) if isinstance(skill.get("actions", []), list) else []:
            if isinstance(action, dict) and action.get("target") == "ally_template" and (not isinstance(action.get("target_template"), str) or action.get("target_template") not in disciples):
                errors.append(f"{where}: target_template 必须引用已有弟子")

    for disciple_id, disciple in disciples.items():
        where = f"config/disciples/{disciple_id}.json"
        if not isinstance(disciple.get("name"), str):
            errors.append(f"{where}: 缺少字符串字段 'name'")
        if disciple.get("origin") not in ORIGINS:
            errors.append(
                f"{where}: origin '{disciple.get('origin')}' 不在 {sorted(ORIGINS)}"
            )
        if disciple.get("rarity") not in RARITIES:
            errors.append(f"{where}: rarity 必须是 1/2/3")
        if disciple.get("lean") not in LEANS:
            errors.append(
                f"{where}: lean '{disciple.get('lean')}' 不在 {sorted(LEANS)}"
            )

        stats = disciple.get("base_stats")
        if not isinstance(stats, dict):
            errors.append(f"{where}: base_stats 必须是对象")
        else:
            for stat in sorted(COMBAT_STATS):
                value = stats.get(stat)
                if not is_number(value) or value <= 0:
                    errors.append(f"{where}: base_stats.{stat} 必须是正数")
            for extra in sorted(set(stats) - COMBAT_STATS):
                errors.append(f"{where}: base_stats 存在未知字段 '{extra}'")

        skill_id = disciple.get("skill")
        if skill_id not in skills:
            errors.append(f"{where}: skill '{skill_id}' 不存在于 config/skills")
        elif skills[skill_id].get("type") != "active":
            errors.append(f"{where}: skill '{skill_id}' 的 type 必须是 active")

        passive_id = disciple.get("passive")
        if passive_id not in skills:
            errors.append(f"{where}: passive '{passive_id}' 不存在于 config/skills")
        elif skills[passive_id].get("type") != "passive":
            errors.append(f"{where}: passive '{passive_id}' 的 type 必须是 passive")

        bond_list = disciple.get("bonds")
        if not isinstance(bond_list, list):
            errors.append(f"{where}: bonds 必须是数组")
        else:
            for i, bond_id in enumerate(bond_list):
                if bond_id not in bonds:
                    errors.append(
                        f"{where}: bonds[{i}] '{bond_id}' 不存在于 config/bonds"
                    )

        asset_id = disciple.get("asset_id")
        if not isinstance(asset_id, str):
            errors.append(f"{where}: asset_id 必须是字符串")
        elif asset_id not in pending and not (
            assets_dir / f"{asset_id}.png"
        ).is_file():
            errors.append(
                f"{where}: asset_id '{asset_id}' 缺少 "
                f"frontend/public/assets/{asset_id}.png，"
                f"也未登记在 config/assets_pending.json"
            )

    for bond_id, bond in bonds.items():
        where = f"config/bonds/{bond_id}.json"
        if not isinstance(bond.get("name"), str):
            errors.append(f"{where}: 缺少字符串字段 'name'")
        members = bond.get("members")
        if not isinstance(members, list) or not members:
            errors.append(f"{where}: members 必须是非空数组")
            continue
        for i, member in enumerate(members):
            if member not in disciples:
                errors.append(
                    f"{where}: members[{i}] '{member}' 不存在于 config/disciples"
                )
        if len(set(member for member in members if isinstance(member, str))) != len(members):
            errors.append(f"{where}: members 不能重复")
        requires = bond.get("requires", len(members))
        if (
            not isinstance(requires, int)
            or isinstance(requires, bool)
            or not 1 <= requires <= len(members)
        ):
            errors.append(f"{where}: requires 必须是 1..{len(members)} 的整数")
        check_effects(bond, where, errors)
        modifiers = bond.get("modifiers")
        if modifiers is not None:
            check_modifiers(modifiers, f"{where}.modifiers", skills, errors)
            member_skills = {disciples[member].get("skill") for member in members if isinstance(member, str) and member in disciples}
            for modifier in modifiers if isinstance(modifiers, list) else []:
                if not isinstance(modifier, dict):
                    continue
                if not isinstance(modifier.get("skill"), str) or modifier.get("skill") not in member_skills:
                    errors.append(f"{where}: 只能修饰羁绊成员的主动技能")
                for action in modifier.get("extra_actions", []) if isinstance(modifier.get("extra_actions", []), list) else []:
                    if isinstance(action, dict) and action.get("target") == "ally_template" and action.get("target_template") not in members:
                        errors.append(f"{where}: 羁绊额外动作的 target_template 必须是羁绊成员")
        for effect in bond.get("effects", []) if isinstance(bond.get("effects", []), list) else []:
            if isinstance(effect, dict) and effect.get("scope") != "duty":
                errors.append(f"{where}: 出征羁绊使用 modifiers，effects 仅保留值守效果")
        if not modifiers and not bond.get("effects"):
            errors.append(f"{where}: 羁绊必须包含可执行的技能修饰或值守效果")

    for enemy_id, enemy in enemies.items():
        where = f"config/enemies/{enemy_id}.json"
        if not isinstance(enemy.get("name"), str):
            errors.append(f"{where}: 缺少字符串字段 'name'")
        stats = enemy.get("base_stats")
        if not isinstance(stats, dict) or set(stats) != COMBAT_STATS:
            errors.append(f"{where}: base_stats 必须包含 hp/atk/def/spd")
        else:
            for stat, value in stats.items():
                if not is_finite_number(value) or value <= 0:
                    errors.append(f"{where}: base_stats.{stat} 必须是有限正数")
        for key, kind in (("skill", "active"), ("passive", "passive")):
            skill = enemy.get(key)
            if skill is not None:
                if not isinstance(skill, dict):
                    errors.append(f"{where}.{key}: 必须是技能对象")
                else:
                    check_skill(skill, f"{where}.{key}", errors)
                    if skill.get("type") != kind:
                        errors.append(f"{where}.{key}: type 必须是 {kind}")

    for material_id, material in materials.items():
        where = f"config/materials/{material_id}.json"
        if not isinstance(material.get("name"), str):
            errors.append(f"{where}: 缺少字符串字段 'name'")
        tier = material.get("tier", 1)
        if not isinstance(tier, int) or isinstance(tier, bool) or tier < 1:
            errors.append(f"{where}: tier 必须是正整数")

    for recipe_id, recipe in recipes.items():
        where = f"config/recipes/{recipe_id}.json"
        if not isinstance(recipe.get("name"), str):
            errors.append(f"{where}: 缺少字符串字段 'name'")
        if recipe.get("kind") not in RECIPE_KINDS:
            errors.append(
                f"{where}: kind '{recipe.get('kind')}' 不在 {sorted(RECIPE_KINDS)}"
            )
        inputs = recipe.get("inputs")
        if not isinstance(inputs, dict) or not inputs:
            errors.append(f"{where}: inputs 必须是非空对象")
        else:
            for material_id, count in inputs.items():
                if material_id not in materials:
                    errors.append(
                        f"{where}: 材料 '{material_id}' 不存在于 config/materials"
                    )
                if not isinstance(count, int) or isinstance(count, bool) or count < 1:
                    errors.append(f"{where}: inputs['{material_id}'] 必须是正整数")
        check_effects(recipe, where, errors)
        max_uses = recipe.get("max_uses")
        if max_uses is not None:
            check_integer(max_uses, 1, 10, f"{where}.max_uses", errors)
            if recipe.get("kind") != "pill":
                errors.append(f"{where}: 只有丹药可以设置 max_uses")
        special = recipe.get("special")
        if special is not None:
            if recipe.get("kind") != "pill":
                errors.append(f"{where}: 只有丹药可以使用 special")
            elif special not in {"heal", "realm"}:
                errors.append(f"{where}: 未实现的丹药效果 '{special}'")
            if recipe.get("effects"):
                errors.append(f"{where}: 特殊丹药不能同时配置 effects")
        elif recipe.get("kind") == "pill" and not recipe.get("effects"):
            errors.append(f"{where}: 丹药必须配置 effects 或 special")

    weapon_templates: dict[str, str] = {}
    for weapon_id, weapon in weapons.items():
        where = f"config/weapons/{weapon_id}.json"
        if not isinstance(weapon.get("name"), str):
            errors.append(f"{where}: 缺少字符串字段 'name'")
        template_id = weapon.get("template_id")
        if not isinstance(template_id, str) or template_id not in disciples:
            errors.append(f"{where}: template_id '{template_id}' 不存在于 config/disciples")
        elif template_id in weapon_templates:
            errors.append(
                f"{where}: 弟子 '{template_id}' 已拥有专武 "
                f"'{weapon_templates[template_id]}'，每名弟子只能有一把"
            )
        else:
            weapon_templates[template_id] = weapon_id

        stats = weapon.get("stats")
        if not isinstance(stats, dict) or not stats:
            errors.append(f"{where}: stats 必须是非空对象")
        else:
            for stat, value in stats.items():
                if stat not in WEAPON_STATS:
                    errors.append(f"{where}: stats 存在未实现属性 '{stat}'")
                if not is_finite_number(value) or not 0 < value <= 1:
                    errors.append(f"{where}: stats.{stat} 必须是 0..1 的有限正数")

        inputs = weapon.get("inputs")
        if not isinstance(inputs, dict) or not inputs:
            errors.append(f"{where}: inputs 必须是非空对象")
        else:
            for material_id, count in inputs.items():
                if material_id not in materials:
                    errors.append(f"{where}: 材料 '{material_id}' 不存在于 config/materials")
                if not isinstance(count, int) or isinstance(count, bool) or count < 1:
                    errors.append(f"{where}: inputs['{material_id}'] 必须是正整数")

        unlock = weapon.get("unlock")
        if not isinstance(unlock, dict):
            errors.append(f"{where}: unlock 必须是对象")
        else:
            for key in ("floor", "level"):
                value = unlock.get(key)
                if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                    errors.append(f"{where}: unlock.{key} 必须是正整数")

    for affix_id, affix in affixes.items():
        where = f"config/affixes/{affix_id}.json"
        if not isinstance(affix.get("name"), str):
            errors.append(f"{where}: 缺少字符串字段 'name'")
        if not isinstance(affix.get("group"), str):
            errors.append(f"{where}: 缺少字符串字段 'group'")
        if affix.get("type") not in AFFIX_TYPES:
            errors.append(f"{where}: type '{affix.get('type')}' 不在 {sorted(AFFIX_TYPES)}")
        if not isinstance(affix.get("description"), str):
            errors.append(f"{where}: 缺少字符串字段 'description'")
        check_effects(affix, where, errors)

        for key, value in (affix.get("bonuses") or {}).items():
            if key not in AFFIX_BONUS_KEYS:
                errors.append(f"{where}: bonuses.{key} 不在 {sorted(AFFIX_BONUS_KEYS)}")
            if not is_number(value) or value < 0:
                errors.append(f"{where}: bonuses.{key} 必须是非负数")

        conditional = affix.get("conditional") or []
        if affix.get("type") == "cond" and not conditional:
            errors.append(f"{where}: type 为 cond 但缺少 conditional")
        for i, extra in enumerate(conditional):
            if extra.get("condition") not in CONDITIONS:
                errors.append(
                    f"{where}: conditional[{i}].condition '{extra.get('condition')}' "
                    f"不在 {sorted(CONDITIONS)}"
                )
            for key, value in (extra.get("bonuses") or {}).items():
                if key not in AFFIX_BONUS_KEYS:
                    errors.append(
                        f"{where}: conditional[{i}].bonuses.{key} 不在 {sorted(AFFIX_BONUS_KEYS)}"
                    )
                if not is_number(value) or value < 0:
                    errors.append(f"{where}: conditional[{i}].bonuses.{key} 必须是非负数")

    for mode_id, mode in modes.items():
        where = f"config/modes/{mode_id}.json"
        if not isinstance(mode.get("name"), str):
            errors.append(f"{where}: 缺少字符串字段 'name'")
        encounters = mode.get("encounters")
        if encounters is not None or (mode.get("enabled") and mode_id == "tower"):
            if not isinstance(encounters, dict) or set(encounters) != {"battle", "elite", "boss"}:
                errors.append(f"{where}: encounters 必须包含 battle/elite/boss")
            else:
                for kind, roster in encounters.items():
                    if not isinstance(roster, list) or not 1 <= len(roster) <= 6:
                        errors.append(f"{where}.encounters.{kind}: 敌方需要 1..6 人")
                    else:
                        for enemy_id in roster:
                            if not isinstance(enemy_id, str) or enemy_id not in enemies:
                                errors.append(f"{where}.encounters.{kind}: 敌人 '{enemy_id}' 不存在")
        multipliers = mode.get("kind_stat_multiplier")
        if multipliers is not None:
            if not isinstance(multipliers, dict) or set(multipliers) != {"battle", "elite", "boss"}:
                errors.append(f"{where}: kind_stat_multiplier 必须包含 battle/elite/boss")
            else:
                for kind, value in multipliers.items():
                    if not is_finite_number(value) or not 0.5 <= value <= 3:
                        errors.append(f"{where}: kind_stat_multiplier.{kind} 必须是 0.5..3 的有限数字")
        variants = mode.get("encounter_variants")
        if variants is not None:
            if not isinstance(variants, dict) or not variants:
                errors.append(f"{where}: encounter_variants 必须是非空对象")
            else:
                for kind, rosters in variants.items():
                    if kind not in {"battle", "elite", "boss"}:
                        errors.append(f"{where}: encounter_variants 存在未知类型 '{kind}'")
                        continue
                    if not isinstance(rosters, list) or not rosters:
                        errors.append(f"{where}.encounter_variants.{kind}: 需要至少一段编成")
                        continue
                    for index, roster in enumerate(rosters):
                        pos = f"{where}.encounter_variants.{kind}[{index}]"
                        if not isinstance(roster, list) or not 1 <= len(roster) <= 6:
                            errors.append(f"{pos}: 敌方需要 1..6 人")
                            continue
                        for enemy_id in roster:
                            if not isinstance(enemy_id, str) or enemy_id not in enemies:
                                errors.append(f"{pos}: 敌人 '{enemy_id}' 不存在")
        for pool_name, index, label in (
            ("enemy_pool", enemies, "config/enemies"),
            ("event_pool", events, "config/events"),
            ("affix_pool", affixes, "config/affixes"),
        ):
            values = mode.get(pool_name, [])
            if not isinstance(values, list):
                errors.append(f"{where}: {pool_name} 必须是数组")
                continue
            for i, ref in enumerate(values):
                if ref not in index:
                    errors.append(
                        f"{where}: {pool_name}[{i}] '{ref}' 不存在于 {label}"
                    )

    return errors


def main() -> int:
    """命令行入口：打印错误明细或通过摘要，返回进程退出码。"""
    errors = validate()
    if errors:
        print(f"[config] {len(errors)} 个错误:")
        for item in errors:
            print(f"  - {item}")
        return 1

    summary = ", ".join(
        f"{name}={len(list((CONFIG_DIR / name).glob('*.json')))}"
        for name in ("skills", "disciples", "bonds", "affixes", "materials", "recipes", "weapons", "modes")
        if (CONFIG_DIR / name).is_dir()
    )
    print(f"[config] ok: {summary}")
    pending = load_pending(CONFIG_DIR)
    if pending:
        print(f"[config] 待生成资产 {len(pending)} 个：{', '.join(sorted(pending))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
