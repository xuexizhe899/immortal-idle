#!/usr/bin/env python3
"""从角色卡生成弟子、技能、羁绊和立绘提示，并做数值与引用校验。

用法：
    python tools/create_disciple.py --brief tools/examples/disciple-brief-sunwukong.json
    python tools/create_disciple.py --brief <角色卡> --apply --allow-pending

默认只写 artifacts/character-drafts/<id>/ 草稿；--apply 才写入 config/。
立绘未生成时默认拒绝上线，必须显式 --allow-pending，避免图鉴出现缺图角色。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from statistics import mean

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
CONFIG_DIR = ROOT / "config"
ASSETS_DIR = ROOT / "frontend" / "public" / "assets"
DEFAULT_OUT = ROOT / "artifacts" / "character-drafts"
sys.path.insert(0, str(TOOLS_DIR))
from validate_config import check_modifiers, check_skill, is_finite_number, validate  # noqa: E402

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,30}$")
ORIGINS = {"sanguo", "myth", "history"}
RARITIES = {1, 2, 3}
LEANS = {"attack", "defense", "support", "craft"}
COMBAT_STATS = {"hp", "atk", "def", "spd"}
YIELD_STATS = {
    "cultivation_rate", "spirit_stone_rate", "stamina_rate",
    "material_rate", "injury_rate",
}
GENERIC_SKILL_NAMES = {"攻击", "技能", "被动", "绝招", "大招", "招式", "本领", "法术", "能力"}

# 同品质基准战力：按现有 16 人的品质/倾向中位数校准。
# 攻/防保留战斗定位，辅/炼因值守价值略低于同品质均值，但不复制诸葛亮的低战力异常。
POWER_TARGETS = {
    (1, "attack"): 27.0, (1, "defense"): 27.5,
    (1, "support"): 26.5, (1, "craft"): 26.0,
    (2, "attack"): 34.0, (2, "defense"): 36.0,
    (2, "support"): 30.5, (2, "craft"): 28.5,
    (3, "attack"): 38.0, (3, "defense"): 40.5,
    (3, "support"): 34.5, (3, "craft"): 34.0,
}

# 每一档的初始形态，最终会等比缩放到目标战力；spd 不进战力公式，只限制在现有区间。
STAT_TEMPLATES = {
    (1, "attack"): {"hp": 100, "atk": 17, "def": 9, "spd": 12},
    (1, "defense"): {"hp": 122, "atk": 12, "def": 15, "spd": 10},
    (1, "support"): {"hp": 92, "atk": 12, "def": 11, "spd": 10},
    (1, "craft"): {"hp": 90, "atk": 13, "def": 8, "spd": 12},
    (2, "attack"): {"hp": 105, "atk": 19, "def": 9, "spd": 13},
    (2, "defense"): {"hp": 138, "atk": 14, "def": 18, "spd": 10},
    (2, "support"): {"hp": 99, "atk": 14, "def": 12, "spd": 12},
    (2, "craft"): {"hp": 92, "atk": 14, "def": 9, "spd": 13},
    (3, "attack"): {"hp": 116, "atk": 20, "def": 11, "spd": 13},
    (3, "defense"): {"hp": 145, "atk": 16, "def": 20, "spd": 10},
    (3, "support"): {"hp": 105, "atk": 15, "def": 14, "spd": 12},
    (3, "craft"): {"hp": 100, "atk": 16, "def": 11, "spd": 13},
}

# 同倾向的两种形态，缩放后总战力仍回到同一目标。
PROFILES = {
    "attack": {
        "burst": {"hp": 0.92, "atk": 1.08, "def": 0.88, "spd": 1.06},
        "bruiser": {"hp": 1.08, "atk": 0.94, "def": 1.10, "spd": 0.94},
    },
    "defense": {
        "guardian": {"hp": 1.06, "atk": 0.92, "def": 1.06, "spd": 0.94},
        "counter": {"hp": 0.96, "atk": 1.08, "def": 1.00, "spd": 1.04},
    },
    "support": {
        "strategist": {"hp": 0.94, "atk": 1.04, "def": 0.96, "spd": 1.08},
        "healer": {"hp": 1.06, "atk": 0.92, "def": 1.04, "spd": 1.02},
    },
    "craft": {
        "alchemist": {"hp": 1.02, "atk": 1.02, "def": 0.94, "spd": 1.02},
        "artisan": {"hp": 1.04, "atk": 0.94, "def": 1.06, "spd": 0.98},
    },
}
DEFAULT_PROFILES = {"attack": "burst", "defense": "guardian", "support": "strategist", "craft": "artisan"}
PROFILE_LABELS = {
    "burst": "爆发", "bruiser": "耐战", "guardian": "守护", "counter": "反击",
    "strategist": "谋略", "healer": "续航", "alchemist": "丹术", "artisan": "器作",
}

COSTS = {
    (1, "attack"): 80, (1, "defense"): 80, (1, "support"): 80, (1, "craft"): 80,
    (2, "attack"): 150, (2, "defense"): 140, (2, "support"): 140, (2, "craft"): 130,
    (3, "attack"): 200, (3, "defense"): 190, (3, "support"): 190, (3, "craft"): 180,
}

ACTIVE_DEFAULTS = {
    "attack": [{"kind": "damage", "target": "enemy_first", "coefficient": 2.0}],
    "defense": [{"kind": "shield", "target": "ally_lowest", "count": 3, "coefficient": 1.4, "duration": 2}],
    "support": [{"kind": "buff", "target": "all_allies", "count": 6, "stat": "atk", "value": .12, "duration": 2}],
    "craft": [{"kind": "heal", "target": "ally_lowest", "count": 2, "coefficient": 1.8}],
}
PASSIVE_DEFAULTS = {"attack": "damage", "defense": "def", "support": "shielding", "craft": "healing"}

STAT_NAMES = {
    "hp": "气血", "atk": "攻击", "def": "防御", "spd": "身法",
    "cultivation_rate": "修为产出", "spirit_stone_rate": "灵石产出",
    "stamina_rate": "行动力恢复", "material_rate": "材料产出", "injury_rate": "伤势恢复",
    "damage": "伤害", "healing": "治疗", "shielding": "护盾",
}
ORIGIN_NAMES = {"sanguo": "三国", "myth": "神话", "history": "历史"}
LEAN_NAMES = {"attack": "攻击", "defense": "防御", "support": "辅助", "craft": "炼制"}
LEAN_DUTY = {"attack": "修为", "defense": "灵石", "support": "行动力/伤势", "craft": "材料"}
SCOPE_NAMES = {"battle": "出征", "run": "局内", "duty": "值守", "permanent": "永久"}
STAT_RANGES = {"hp": (80, 170), "atk": (10, 26), "def": (6, 24), "spd": (7, 15)}
# 与 backend/app/domain/duty.py 的 RARITY_FACTOR / REALM_BONUS 保持一致。
DUTY_RARITY_FACTOR = {1: 0.04, 2: 0.06, 3: 0.09}
DUTY_REALM_BONUS = 0.01


class BriefError(ValueError):
    """角色卡或生成结果不满足约束。"""


def load_json(path: Path) -> dict:
    """读取 UTF-8 JSON。"""
    return json.loads(path.read_text(encoding="utf-8"))


def load_collection(folder: Path) -> dict[str, dict]:
    """按 id 读取目录下的 JSON 配置。"""
    return {
        data["id"]: data
        for path in sorted(folder.glob("*.json"))
        for data in [load_json(path)]
    }


def write_json(path: Path, data: dict) -> None:
    """写入带缩进的 UTF-8 JSON，保持与现有配置一致的格式。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_number(value: object) -> bool:
    """排除 bool，避免 True 被当成 1。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def base_power(stats: dict[str, float]) -> float:
    """沿用原型基础参考分校准属性区间，不预测自动战斗胜负。"""
    return stats["atk"] + stats["def"] * 0.5 + stats["hp"] * 0.1


def effect_text(effect: dict) -> str:
    """把效果转成报告里的中文短句。"""
    name = STAT_NAMES.get(effect["stat"], effect["stat"])
    return f"{name} +{effect['value'] * 100:.0f}%（{SCOPE_NAMES.get(effect['scope'], effect['scope'])}）"


def skill_text(skill: dict) -> str:
    """报告直接描述执行配置，避免把参考分当作技能强度结论。"""
    if skill["type"] == "passive":
        return " / ".join(f"{STAT_NAMES[stat]} +{value:.0%}" for stat, value in skill["bonuses"].items()) + f"；条件 {skill['condition']}"
    kinds = {"damage": "伤害", "heal": "治疗", "shield": "护盾", "buff": "属性增减"}
    actions = []
    for action in skill["actions"]:
        amount = f"{action['value']:+.0%} {STAT_NAMES[action['stat']]}" if action["kind"] == "buff" else f"{action.get('coefficient', 1):.0%} 攻击"
        actions.append(f"{kinds[action['kind']]} {amount} × {action.get('count', 1)}；目标 {action['target']}")
    return " / ".join(actions) + f"；每 {skill['cooldown']} 次自身行动施放"


def has_motif(text: str, motifs: list[str]) -> bool:
    """技能或视觉描述至少要落在一个角色母题上，避免通用模板文案。"""
    return any(motif in text for motif in motifs)


def text_field(brief: dict, key: str, label: str, minimum: int, maximum: int | None = None) -> str:
    """读取并校验角色卡里的中文文本字段。"""
    value = brief.get(key)
    if not isinstance(value, str) or len(value.strip()) < minimum:
        raise BriefError(f"{label}至少需要 {minimum} 个字符")
    value = value.strip()
    if maximum is not None and len(value) > maximum:
        raise BriefError(f"{label}不能超过 {maximum} 个字符")
    return value


def validate_effect(effect: dict, *, kind: str) -> dict:
    """只保留已实现的值守羁绊效果；战斗技能改由动作与被动加成执行。"""
    stat = effect.get("stat")
    mode = effect.get("mode", "add_pct")
    scope = effect.get("scope")
    value = effect.get("value")
    if mode != "add_pct":
        raise BriefError(f"{kind} 目前只接受 add_pct 模式")
    if scope == "duty":
        if stat not in YIELD_STATS:
            raise BriefError(f"{kind} 的值守效果只能使用产出类属性")
        low, high = 0.06, 0.18
    else:
        raise BriefError(f"{kind} 的 effects 只接受 duty，出征羁绊请使用 modifiers")
    if not is_finite_number(value) or not low <= value <= high:
        raise BriefError(f"{kind} 的数值必须在 {low:.0%}–{high:.0%} 之间")
    return {"stat": stat, "mode": mode, "value": float(value), "scope": scope}


def make_skill(kind: str, brief: dict) -> dict:
    """生成与服务端一致的可执行技能，旧百分比资料字段不能静默接入。"""
    source = brief[kind]
    allowed = {"name", "description"} | ({"actions", "cooldown", "vfx"} if kind == "active" else {"bonuses", "condition"})
    unknown = set(source) - allowed
    if unknown:
        raise BriefError(f"{kind} 不支持字段 {sorted(unknown)}；主动使用 actions，被动使用 bonuses")
    skill = {
        "id": f"{brief['id']}-{'art' if kind == 'active' else 'passive'}",
        "name": source["name"], "type": kind,
        "description": source["description"], "effects": [],
    }
    if kind == "active":
        skill.update(
            cooldown=source.get("cooldown", 3), vfx=source.get("vfx", "strike"),
            actions=source.get("actions", [dict(action) for action in ACTIVE_DEFAULTS[brief["lean"]]]),
        )
    else:
        skill.update(
            bonuses=source.get("bonuses", {PASSIVE_DEFAULTS[brief["lean"]]: {1: .08, 2: .1, 3: .12}[brief["rarity"]]}),
            condition=source.get("condition", "always"),
        )
    errors: list[str] = []
    check_skill(skill, kind, errors)
    if errors:
        raise BriefError("技能不可执行：" + "；".join(errors))
    # 内容工具的安全预算比引擎上限更窄；配置可执行不等于适合直接上线。
    if kind == "active":
        if not 2 <= skill["cooldown"] <= 5:
            raise BriefError("生成角色的主动 cooldown 必须在 2–5 次自身行动之间")
        budget = 0.0
        for action in skill["actions"]:
            if action["kind"] == "buff":
                if abs(action["value"]) > .3:
                    raise BriefError("生成角色的单条属性增减不能超过 30%")
                budget += abs(action["value"]) * action.get("count", 1) * 3
            else:
                coefficient = action.get("coefficient", 1)
                if coefficient > 3:
                    raise BriefError("生成角色的单目标伤害、治疗与护盾系数不能超过 300%")
                budget += coefficient * action.get("count", 1)
        if budget > 10:
            raise BriefError("生成角色的主动总效果预算超过 10，请减少目标、系数或增减益")
    elif any(value > .3 for value in skill["bonuses"].values()) or sum(skill["bonuses"].values()) > .4:
        raise BriefError("生成角色被动单属性不能超过 30%，合计不能超过 40%")
    return skill


def make_bond(source: object, new_id: str, disciples: dict[str, dict], bonds: dict[str, dict], skills: dict[str, dict]) -> dict | None:
    """生成可选羁绊；不覆盖既有羁绊，避免误改其他角色。"""
    if source is None:
        return None
    if not isinstance(source, dict):
        raise BriefError("bond 必须是对象或 null")
    bond_id = source.get("id")
    if not isinstance(bond_id, str) or not ID_PATTERN.fullmatch(bond_id):
        raise BriefError("羁绊 id 必须是小写字母开头的 3–31 位 slug")
    if bond_id in bonds:
        raise BriefError(f"羁绊 id '{bond_id}' 已存在；请换一个 id，或手动合并到现有羁绊")
    name = text_field(source, "name", "羁绊名称", 2, 8)
    members = source.get("members")
    if not isinstance(members, list) or not members:
        raise BriefError("羁绊 members 必须是非空数组")
    if new_id not in members:
        raise BriefError("羁绊 members 必须包含新角色 id")
    for member in members:
        if not isinstance(member, str) or (member != new_id and member not in disciples):
            raise BriefError(f"羁绊成员 '{member}' 不存在于现有弟子")
    if len(set(members)) != len(members):
        raise BriefError("羁绊 members 不能重复，同一位弟子只能计数一次")
    requires = source.get("requires", len(members))
    if not isinstance(requires, int) or isinstance(requires, bool) or not 1 <= requires <= len(members):
        raise BriefError(f"羁绊 requires 必须是 1–{len(members)} 的整数")
    raw_effects = source.get("effects", [])
    if not isinstance(raw_effects, list) or len(raw_effects) > 2:
        raise BriefError("羁绊 effects 最多接受两条值守效果")
    effects = []
    for raw in raw_effects:
        if not isinstance(raw, dict):
            raise BriefError("羁绊效果必须是对象")
        effect = validate_effect(raw, kind="羁绊")
        effects.append(effect)
    modifiers = source.get("modifiers", [])
    if modifiers:
        errors: list[str] = []
        check_modifiers(modifiers, "bond.modifiers", skills, errors)
        member_skills = {f"{new_id}-art"} | {disciples[member]["skill"] for member in members if member in disciples}
        for modifier in modifiers if isinstance(modifiers, list) else []:
            if isinstance(modifier, dict) and modifier.get("skill") not in member_skills:
                errors.append("只能修饰本羁绊成员的主动技能")
        if errors:
            raise BriefError("羁绊不可执行：" + "；".join(errors))
        for modifier in modifiers:
            if modifier.get("add_targets", 0) > 2 or modifier.get("coefficient_bonus", 0) > .3 or modifier.get("duration_bonus", 0) > 2:
                raise BriefError("生成羁绊最多追加2个目标、30%系数或2回合持续时间")
            for action in modifier.get("extra_actions", []):
                if action["kind"] == "buff" and abs(action["value"]) > .3:
                    raise BriefError("羁绊额外动作的属性增减不能超过30%")
                if action["kind"] != "buff" and action.get("coefficient", 1) > 2:
                    raise BriefError("羁绊额外动作的系数不能超过200%")
                if action.get("target") == "ally_template" and action.get("target_template") not in members:
                    raise BriefError("羁绊额外动作的指定目标必须是羁绊成员")
    if not effects and not modifiers:
        raise BriefError("羁绊需要 modifiers 技能修饰或已实现的值守 effects")
    return {"id": bond_id, "name": name, "description": source.get("description", ""), "members": members, "requires": requires, "effects": effects, **({"modifiers": modifiers} if modifiers else {})}


def validate_brief(
    brief: dict, disciples: dict[str, dict], skills: dict[str, dict],
    bonds: dict[str, dict], *, force: bool,
) -> dict:
    """校验角色卡并补全默认值；返回规范化后的输入。"""
    if not isinstance(brief, dict):
        raise BriefError("角色卡顶层必须是对象")
    brief = dict(brief)
    char_id = brief.get("id")
    if not isinstance(char_id, str) or not ID_PATTERN.fullmatch(char_id):
        raise BriefError("id 必须是小写字母开头的 3–31 位 slug")
    if char_id in disciples and not force:
        raise BriefError(f"弟子 id '{char_id}' 已存在；如需覆盖请显式使用 --force")
    if f"{char_id}-art" in skills and not force:
        raise BriefError(f"技能 id '{char_id}-art' 已存在；如需覆盖请显式使用 --force")
    brief["name"] = text_field(brief, "name", "角色名称", 1, 12)
    brief["title"] = text_field(brief, "title", "称号", 1, 8)
    if brief.get("origin") not in ORIGINS:
        raise BriefError(f"origin 必须是 {sorted(ORIGINS)} 之一")
    if brief.get("rarity") not in RARITIES:
        raise BriefError("rarity 必须是 1/2/3")
    lean = brief.get("lean")
    if lean not in LEANS:
        raise BriefError(f"lean 必须是 {sorted(LEANS)} 之一")
    profile = brief.get("profile", DEFAULT_PROFILES[lean])
    if profile not in PROFILES[lean]:
        raise BriefError(f"{lean} 倾向的 profile 必须是 {sorted(PROFILES[lean])}")
    brief["profile"] = profile
    brief["concept"] = text_field(brief, "concept", "角色概念", 20)
    brief["visual"] = text_field(brief, "visual", "视觉描述", 30)
    motifs = brief.get("motifs")
    if not isinstance(motifs, list) or not 2 <= len(motifs) <= 6:
        raise BriefError("motifs 需要 2–6 个角色母题")
    motifs = [text_field({"motif": item}, "motif", "母题", 2, 12) for item in motifs]
    if len(set(motifs)) != len(motifs):
        raise BriefError("motifs 不能重复")
    if not has_motif(brief["visual"], motifs):
        raise BriefError("视觉描述至少要包含一个母题，保证立绘提示与角色一致")
    brief["motifs"] = motifs
    for key, label in (("active", "主动招式"), ("passive", "被动")):
        source = brief.get(key)
        if not isinstance(source, dict):
            raise BriefError(f"{key} 必须是对象")
        source = dict(source)
        source["name"] = text_field(source, "name", f"{label}名称", 2, 10)
        source["description"] = text_field(source, "description", f"{label}描述", 12)
        if source["name"] in GENERIC_SKILL_NAMES:
            raise BriefError(f"{label}名称不能使用通用词「{source['name']}」")
        if not has_motif(source["description"], motifs):
            raise BriefError(f"{label}描述至少要包含一个母题，避免通用文案")
        brief[key] = source
    if brief["active"]["name"] == brief["passive"]["name"]:
        raise BriefError("主动招式和被动名称不能相同")
    unlock = brief.get("unlock_cost")
    if unlock is not None:
        if not isinstance(unlock, dict) or set(unlock) - {"reputation"}:
            raise BriefError("unlock_cost 只支持 reputation")
        reputation = unlock.get("reputation")
        if not isinstance(reputation, int) or isinstance(reputation, bool) or not 40 <= reputation <= 300:
            raise BriefError("unlock_cost.reputation 必须是 40–300 的整数")
    asset_id = brief.get("asset_id", f"trial-v04/{char_id}")
    if (
        not isinstance(asset_id, str)
        or not re.fullmatch(r"[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*", asset_id)
    ):
        raise BriefError("asset_id 必须是无扩展名的安全相对路径，例如 trial-v04/sunwukong")
    brief["asset_id"] = asset_id
    power_target = brief.get("power_target", POWER_TARGETS[(brief["rarity"], lean)])
    if not is_number(power_target):
        raise BriefError("power_target 必须是数字")
    base = POWER_TARGETS[(brief["rarity"], lean)]
    if not base - 1.5 <= power_target <= base + 1.5:
        raise BriefError(f"power_target 必须接近 {brief['rarity']} 品 {lean} 基准 {base:g}（±1.5）")
    brief["power_target"] = float(power_target)
    return brief


def generate_stats(brief: dict) -> dict[str, int]:
    """按模板、形态和目标战力生成整数属性。"""
    key = (brief["rarity"], brief["lean"])
    template = STAT_TEMPLATES[key]
    multipliers = PROFILES[brief["lean"]][brief["profile"]]
    shaped = {stat: value * multipliers.get(stat, 1.0) for stat, value in template.items()}
    target = brief["power_target"]
    scale = target / base_power(shaped)
    stats = {
        "hp": round(shaped["hp"] * scale),
        "atk": round(shaped["atk"] * scale),
        "def": round(shaped["def"] * scale),
        "spd": round(shaped["spd"]),
    }
    for stat, (low, high) in STAT_RANGES.items():
        stats[stat] = min(high, max(low, int(stats[stat])))
    step = 1 if base_power(stats) < target else -1
    low, high = STAT_RANGES["hp"]
    while abs(base_power(stats) - target) > 0.051 and low <= stats["hp"] + step <= high:
        stats["hp"] += step
    return stats


def build_art_prompt(brief: dict, style: dict, asset_id: str) -> dict:
    """把全局像素风格与角色视觉合并为生图提示，不调用生图接口。"""
    visual_prompt = brief.get("visual_prompt") or brief["visual"]
    status = "ready" if (ASSETS_DIR / f"{asset_id}.png").is_file() else "pending"
    return {
        "asset_id": asset_id,
        "status": status,
        "style_source": "config/style/style.json",
        "prompt": f"{style['style_prompt']}, {visual_prompt}",
        "negative_prompt": style["negative_prompt"],
        "size": style["size"],
        "fallback_size": style["fallback_size"],
        "palette": style["palette"],
        "motifs": brief["motifs"],
        "visual": brief["visual"],
    }


def peer_text(disciples: dict[str, dict], rarity: int, lean: str, exclude_id: str) -> tuple[str, list[float]]:
    """同品质同倾向的对照文本与战力列表。"""
    peers = [
        (data["name"], base_power(data["base_stats"]))
        for data in disciples.values()
        if data["rarity"] == rarity and data["lean"] == lean and data["id"] != exclude_id
    ]
    if not peers:
        return "同组暂无对照", []
    peers.sort(key=lambda item: item[1])
    text = "、".join(f"{name} {power:.2f}" for name, power in peers)
    return f"{text}；均值 {mean(power for _, power in peers):.2f}", [power for _, power in peers]


def build_report(package: dict, disciples: dict[str, dict]) -> str:
    """生成可审阅的数值报告。"""
    brief = package["brief"]
    stats = package["disciple"]["base_stats"]
    power = base_power(stats)
    peers_text, peers = peer_text(disciples, brief["rarity"], brief["lean"], brief["id"])
    rarity_powers = [
        base_power(data["base_stats"]) for data in disciples.values()
        if data["rarity"] == brief["rarity"] and data["id"] != brief["id"]
    ]
    rarity_range = (
        f"{min(rarity_powers):.2f}–{max(rarity_powers):.2f}"
        if rarity_powers else "暂无同品质角色"
    )
    relation = []
    if peers:
        group_means = {
            stat: mean(data["base_stats"][stat] for data in disciples.values()
                       if data["rarity"] == brief["rarity"] and data["lean"] == brief["lean"]
                       and data["id"] != brief["id"])
            for stat in ("hp", "atk", "def", "spd")
        }
        for stat in ("atk", "def", "spd"):
            if stats[stat] > group_means[stat] * 1.03:
                relation.append(f"{STAT_NAMES[stat]}高于同组")
            elif stats[stat] < group_means[stat] * 0.97:
                relation.append(f"{STAT_NAMES[stat]}低于同组")
            else:
                relation.append(f"{STAT_NAMES[stat]}接近同组")
    relation_text = "，".join(relation) if relation else "同组暂无对照"
    duty_value = DUTY_RARITY_FACTOR[brief["rarity"]] + DUTY_REALM_BONUS
    bond = package["bond"]
    bond_names = ""
    if bond:
        member_names = [
            brief["name"] if member == brief["id"] else disciples.get(member, {}).get("name", member)
            for member in bond["members"]
        ]
        bond_names = f"- 羁绊：{bond['name']}（{' / '.join(member_names)}，{len(bond.get('modifiers', []))} 条技能修饰，{len(bond['effects'])} 条值守效果）"
    lines = [
        f"# 角色数值报告：{brief['name']}",
        "",
        f"- 角色：{brief['name']} · {brief['title']}（{ORIGIN_NAMES[brief['origin']]} / {brief['rarity']} 品 / {LEAN_NAMES[brief['lean']]} / {PROFILE_LABELS[brief['profile']]}）",
        f"- 目标基础参考分：{brief['power_target']:.2f}（{brief['rarity']} 品{LEAN_NAMES[brief['lean']]}基准）",
        f"- 实际基础参考分：{power:.2f}（偏差 {(power - brief['power_target']) / brief['power_target'] * 100:+.2f}%）",
        f"- 基础属性：气血 {stats['hp']} / 攻击 {stats['atk']} / 防御 {stats['def']} / 身法 {stats['spd']}",
        f"- 同组对照（{brief['rarity']} 品{LEAN_NAMES[brief['lean']]}）：{peers_text}",
        f"- 同品质范围：{rarity_range}",
        f"- 值守价值：品质系数 {DUTY_RARITY_FACTOR[brief['rarity']]:.3f} + 境界 {DUTY_REALM_BONUS:.2f} = {duty_value:.1%}（{LEAN_DUTY[brief['lean']]}产出加成）",
        f"- 招募声望：{package['disciple']['unlock_cost']['reputation']}",
        f"- 主动招式：{package['active']['name']}（{skill_text(package['active'])}）",
        f"  {package['active']['description']}",
        f"- 被动：{package['passive']['name']}（{skill_text(package['passive'])}）",
        f"  {package['passive']['description']}",
        bond_names or "- 羁绊：无",
        f"- 立绘：{'已就绪' if package['art']['status'] == 'ready' else '待生成'}（{brief['asset_id']}）",
        f"- 风格母题：{'、'.join(brief['motifs'])}",
        f"- 属性检查：基础参考分 {power:.2f}，位于同品质 {rarity_range} 区间内；{relation_text}，符合「{PROFILE_LABELS[brief['profile']]}」定位。",
        "- 战斗平衡：参考分仅校准属性，技能与羁绊仍需在同等级、同敌人条件下模拟验收。",
        "",
        "> 草稿目录可直接审阅；立绘完成前请勿 `--apply`，除非显式使用 `--allow-pending`。",
        "> 新羁绊涉及既有角色时，apply 会把这些角色的图鉴羁绊列表同步加上该羁绊。",
    ]
    return "\n".join(lines) + "\n"


def build_package(brief: dict, *, force: bool = False, config_dir: Path = CONFIG_DIR) -> dict:
    """生成完整角色包，不写磁盘。"""
    disciples = load_collection(config_dir / "disciples")
    skills = load_collection(config_dir / "skills")
    bonds = load_collection(config_dir / "bonds")
    brief = validate_brief(brief, disciples, skills, bonds, force=force)
    stats = generate_stats(brief)
    power = base_power(stats)
    if abs(power - brief["power_target"]) > 0.6:
        raise BriefError(f"生成战力 {power:.2f} 偏离目标 {brief['power_target']:.2f} 过多")
    for stat, (low, high) in STAT_RANGES.items():
        if not low <= stats[stat] <= high:
            raise BriefError(f"{STAT_NAMES[stat]} {stats[stat]} 超出安全范围 {low}–{high}")
    rarity_powers = [
        base_power(data["base_stats"]) for data in disciples.values()
        if data["rarity"] == brief["rarity"] and data["id"] != brief["id"]
    ]
    if rarity_powers and not min(rarity_powers) - 2 <= power <= max(rarity_powers) + 2:
        raise BriefError("生成战力超出同品质现有区间，请降低 power_target 或调整品质/倾向")
    active = make_skill("active", brief)
    passive = make_skill("passive", brief)
    bond = make_bond(brief.get("bond"), brief["id"], disciples, bonds, {**skills, active["id"]: active})
    cost = (brief.get("unlock_cost") or {}).get("reputation", COSTS[(brief["rarity"], brief["lean"])])
    style_path = config_dir / "style" / "style.json"
    if not style_path.is_file():
        raise BriefError("缺少 config/style/style.json，无法生成立绘提示")
    art = build_art_prompt(brief, load_json(style_path), brief["asset_id"])
    disciple = {
        "id": brief["id"],
        "name": brief["name"],
        "title": brief["title"],
        "origin": brief["origin"],
        "rarity": brief["rarity"],
        "lean": brief["lean"],
        "asset_id": brief["asset_id"],
        "base_stats": stats,
        "skill": f"{brief['id']}-art",
        "passive": f"{brief['id']}-passive",
        # 覆盖角色资料时保留既有羁绊，避免图鉴与实际羁绊成员失去对应。
        "bonds": list(dict.fromkeys([
            *disciples.get(brief["id"], {}).get("bonds", []),
            *([bond["id"]] if bond else []),
        ])),
        "unlock_cost": {"reputation": cost},
    }
    package = {
        "brief": brief,
        "disciple": disciple,
        "active": active,
        "passive": passive,
        "bond": bond,
        "art": art,
    }
    package["report"] = build_report(package, disciples)
    return package


def package_files(package: dict) -> dict[Path, dict]:
    """角色包在 config/ 下的相对路径与内容。"""
    char_id = package["brief"]["id"]
    files = {
        Path("disciples") / f"{char_id}.json": package["disciple"],
        Path("skills") / f"{char_id}-art.json": package["active"],
        Path("skills") / f"{char_id}-passive.json": package["passive"],
    }
    if package["bond"]:
        files[Path("bonds") / f"{package['bond']['id']}.json"] = package["bond"]
    return files


def write_package(config_dir: Path, package: dict) -> list[Path]:
    """把角色包写入指定配置树。"""
    written = []
    for relative, data in package_files(package).items():
        target = config_dir / relative
        write_json(target, data)
        written.append(target)
    return written


def update_pending(config_dir: Path, asset_id: str, *, ready: bool) -> None:
    """维护 assets_pending 白名单；立绘就绪时移除，未就绪时登记。"""
    path = config_dir / "assets_pending.json"
    pending: set[str] = set()
    if path.is_file():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            pending = {item for item in raw if isinstance(item, str)}
    if ready:
        pending.discard(asset_id)
    else:
        pending.add(asset_id)
    if not pending and path.exists():
        path.unlink()
        return
    write_json(path, sorted(pending))


def update_member_bonds(config_dir: Path, bond: dict | None, new_id: str) -> list[Path]:
    """新羁绊涉及既有角色时，把羁绊 id 追加到他们的图鉴列表。"""
    if bond is None:
        return []
    changed = []
    for member in bond["members"]:
        if member == new_id:
            continue
        path = config_dir / "disciples" / f"{member}.json"
        if not path.is_file():
            raise BriefError(f"羁绊成员 '{member}' 的配置文件不存在")
        data = load_json(path)
        bonds = data.get("bonds")
        if not isinstance(bonds, list):
            raise BriefError(f"{member}.json 的 bonds 必须是数组")
        if bond["id"] not in bonds:
            bonds.append(bond["id"])
            write_json(path, data)
            changed.append(path)
    return changed


def validate_package(package: dict, *, config_dir: Path = CONFIG_DIR, assets_dir: Path = ASSETS_DIR) -> list[str]:
    """在临时配置副本上验证生成结果，避免坏配置写入正式目录。"""
    with tempfile.TemporaryDirectory() as tmp:
        temp_config = Path(tmp) / "config"
        shutil.copytree(config_dir, temp_config)
        write_package(temp_config, package)
        update_member_bonds(temp_config, package["bond"], package["brief"]["id"])
        if not (assets_dir / f"{package['brief']['asset_id']}.png").is_file():
            update_pending(temp_config, package["brief"]["asset_id"], ready=False)
        return validate(temp_config, assets_dir)


def write_draft(package: dict, out_root: Path = DEFAULT_OUT) -> Path:
    """把草稿、报告和立绘提示写到 artifacts/，不碰正式配置。"""
    char_id = package["brief"]["id"]
    target = out_root / char_id
    target.mkdir(parents=True, exist_ok=True)
    write_json(target / "brief.json", package["brief"])
    write_json(target / "disciple.json", package["disciple"])
    write_json(target / "skill-active.json", package["active"])
    write_json(target / "skill-passive.json", package["passive"])
    if package["bond"]:
        write_json(target / "bond.json", package["bond"])
    elif (target / "bond.json").is_file():
        # 同名草稿取消羁绊后，移除上次生成的羁绊文件，防止审阅旧内容。
        (target / "bond.json").unlink()
    write_json(target / "art-prompt.json", package["art"])
    (target / "balance-report.md").write_text(package["report"], encoding="utf-8")
    return target


def apply_package(
    package: dict, *, config_dir: Path = CONFIG_DIR, assets_dir: Path = ASSETS_DIR,
    force: bool = False, allow_pending: bool = False,
) -> list[Path]:
    """校验通过后写入正式配置；立绘缺失时必须显式允许待生成。"""
    asset_id = package["brief"]["asset_id"]
    ready = (assets_dir / f"{asset_id}.png").is_file()
    if not ready and not allow_pending:
        raise BriefError(f"立绘 {asset_id}.png 尚未生成；请先完成立绘，或显式使用 --allow-pending")
    existing = [path for path in package_files(package) if (config_dir / path).exists()]
    if existing and not force:
        raise BriefError(f"目标文件已存在：{existing[0]}；如需覆盖请显式使用 --force")
    errors = validate_package(package, config_dir=config_dir, assets_dir=assets_dir)
    if errors:
        raise BriefError("临时配置校验未通过：\n" + "\n".join(f"- {item}" for item in errors))
    written = write_package(config_dir, package)
    written.extend(update_member_bonds(config_dir, package["bond"], package["brief"]["id"]))
    update_pending(config_dir, asset_id, ready=ready)
    errors = validate(config_dir, assets_dir)
    if errors:
        raise BriefError("正式配置校验未通过：\n" + "\n".join(f"- {item}" for item in errors))
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="从角色卡生成均衡的弟子配置、技能、羁绊与立绘提示")
    parser.add_argument("--brief", required=True, type=Path, help="角色卡 JSON 路径")
    parser.add_argument("--out", default=DEFAULT_OUT, type=Path, help="草稿输出目录")
    parser.add_argument("--apply", action="store_true", help="写入 config/（默认只写草稿）")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的弟子/技能文件")
    parser.add_argument("--allow-pending", action="store_true", help="允许在立绘未生成时写入配置")
    args = parser.parse_args()
    try:
        package = build_package(load_json(args.brief), force=args.force)
        draft = write_draft(package, args.out)
        errors = validate_package(package)
        print(package["report"])
        print(f"草稿：{draft}")
        if errors:
            print("临时配置校验失败：")
            for error in errors:
                print(f"- {error}")
            return 1
        print("临时配置校验：通过")
        if args.apply:
            written = apply_package(
                package, force=args.force, allow_pending=args.allow_pending,
            )
            print("已写入正式配置：")
            for path in written:
                print(f"- {path.relative_to(ROOT)}")
        return 0
    except BriefError as error:
        print(f"[create_disciple] {error}")
        return 1
    except (OSError, json.JSONDecodeError) as error:
        print(f"[create_disciple] 读取或写入失败：{error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
