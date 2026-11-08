#!/usr/bin/env python3
"""配置校验：结构 + 跨文件引用完整性。

用法：
    python tools/validate_config.py

退出码 1 表示有错误，每条错误都带文件路径与字段名。只用标准库，保证 CI 裸 Python 可跑。
"""

from __future__ import annotations

import json
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
    "pill_rate",
}
STATS = COMBAT_STATS | YIELD_STATS
RECIPE_KINDS = {"pill", "artifact"}


def is_number(value: object) -> bool:
    """判断是否为数字，排除 bool（bool 是 int 的子类，会被误判）。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


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
        if not is_number(effect.get("value")):
            errors.append(f"{pos}: value 必须是数字")


def validate(
    config_dir: Path | None = None, assets_dir: Path | None = None
) -> list[str]:
    """执行全部校验并返回错误列表，空列表表示通过。"""
    config_dir = config_dir or CONFIG_DIR
    assets_dir = assets_dir or ASSETS_DIR
    errors: list[str] = []
    pending = load_pending(config_dir)

    skills = load_collection(config_dir, "skills", errors)
    disciples = load_collection(config_dir, "disciples", errors)
    bonds = load_collection(config_dir, "bonds", errors)
    materials = load_collection(config_dir, "materials", errors)
    recipes = load_collection(config_dir, "recipes", errors)
    affixes = load_collection(config_dir, "affixes", errors)
    enemies = load_collection(config_dir, "enemies", errors)
    events = load_collection(config_dir, "events", errors)
    modes = load_collection(config_dir, "modes", errors)

    for skill_id, skill in skills.items():
        where = f"config/skills/{skill_id}.json"
        if not isinstance(skill.get("name"), str):
            errors.append(f"{where}: 缺少字符串字段 'name'")
        if skill.get("type") not in SKILL_TYPES:
            errors.append(
                f"{where}: type '{skill.get('type')}' 不在 {sorted(SKILL_TYPES)}"
            )
        check_effects(skill, where, errors)

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
        requires = bond.get("requires", len(members))
        if (
            not isinstance(requires, int)
            or isinstance(requires, bool)
            or not 1 <= requires <= len(members)
        ):
            errors.append(f"{where}: requires 必须是 1..{len(members)} 的整数")
        check_effects(bond, where, errors)

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

    for mode_id, mode in modes.items():
        where = f"config/modes/{mode_id}.json"
        if not isinstance(mode.get("name"), str):
            errors.append(f"{where}: 缺少字符串字段 'name'")
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
        for name in ("skills", "disciples", "bonds", "materials", "recipes", "modes")
        if (CONFIG_DIR / name).is_dir()
    )
    print(f"[config] ok: {summary}")
    pending = load_pending(CONFIG_DIR)
    if pending:
        print(f"[config] 待生成资产 {len(pending)} 个：{', '.join(sorted(pending))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
