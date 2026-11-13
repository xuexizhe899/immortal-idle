#!/usr/bin/env python3
"""在内存中复现六人阵容对照及人工 6v6 满回合压力场景。

运行：
    backend/.venv/Scripts/python.exe tools/measure_battles.py --suite t16
    backend/.venv/Scripts/python.exe tools/measure_battles.py --suite t17
    backend/.venv/Scripts/python.exe tools/measure_battles.py --suite t18
    backend/.venv/Scripts/python.exe tools/measure_battles.py --suite t19
    backend/.venv/Scripts/python.exe tools/measure_battles.py --suite t20

仅读取配置与代码，不连接数据库，不读取本地 .env，不改变真实存档。
t16 复跑历史矩阵；t17 增加培养档位、固定策略与真实战报统计；
t19 增加无投入/属性丹/专武/两者兼具的对照，并单独报告材料投入；
t20 复用 t19 投入，在敌人机制与层段编成变更后与 t19 对照。
耗时是当前机器的观测值，不作为跨机器性能承诺；输出包含输入文件指纹。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config_loader import (  # noqa: E402
    load_affixes, load_bonds, load_disciples, load_enemies, load_modes, load_recipes,
    load_skills, load_weapons,
)
from app.domain.battle import ROUND_LIMIT, simulate_battle  # noqa: E402
from app.domain.progression import REALM_UP_RATIOS, upgrade_cost  # noqa: E402
from app.domain.run_engine import (  # noqa: E402
    MAX_PARTY, choose, pick_affix, run_status, settle_run, start_run,
)
from app.models.battle import BattleAction, BattleUnit, SkillDefinition  # noqa: E402
from app.models.save import (  # noqa: E402
    ActiveRun, BattleSummary, DiscipleState, GameState, Resources, RunNode, RunPartySnapshot,
)

SEEDS = (17, 2026, 11012)
LEVELS = (1, 3)
NOW = datetime(2026, 11, 12, 0, 0, tzinfo=timezone.utc)
LINEUPS = {
    "wuhu_benyue": ("guanyu", "zhangfei", "zhaoyun", "houyi", "change", "huatuo"),
    "three_pairs": ("nezha", "yangjian", "houyi", "change", "zhugeliang", "zhouyu"),
    "two_pairs_guard": ("nezha", "yangjian", "zhugeliang", "zhouyu", "yuefei", "huatuo"),
    "mechanics_core": ("houyi", "change", "baisuzhen", "yuefei", "zhaoyun", "huatuo"),
    "highest_rarity": ("guanyu", "nezha", "yangjian", "yuefei", "zhaoyun", "zhugeliang"),
    "low_rarity_substitution": ("houyi", "change", "baisuzhen", "dufu", "jingwei", "huatuo"),
}
T17_TIERS = {
    "early_l1_r1": (1, 1),
    "mid_l3_r1": (3, 1),
    "late_l6_r1": (6, 1),
    "late_l6_r2": (6, 2),
}
T18_TIERS = {
    "early_l1_r1": (1, 1),
    "mid_l3_r1": (3, 1),
    "late_l6_r2": (6, 2),
    "end_l10_r3": (10, 3),
}
T19_TIERS = {
    "mid_l3_r1": (3, 1),
    "late_l6_r2": (6, 2),
    "end_l10_r3": (10, 3),
}
T19_LOADOUTS = {
    "control": (False, False),
    "pills": (True, False),
    "weapons": (False, True),
    "both": (True, True),
}
ATTRIBUTE_PILLS = ("gu_ti_dan", "ju_qi_dan")
ATTRIBUTE_PILL_USES = 3
POLICIES = ("first", "defensive", "aggressive")
POLICY_DESCRIPTIONS = {
    "first": "Always choose route index 0 and affix option index 0 (T16 baseline).",
    "defensive": "Prefer battle nodes over elite; prefer 坚守 (jianshou) affix, then 奇谋 (qimou), then 锋锐 (fengrui).",
    "aggressive": "Prefer elite/boss nodes; prefer 锋锐 (fengrui) affix, then 奇谋 (qimou), then 坚守 (jianshou).",
}
GAMEPLAY_PATHS = (
    ROOT / "config" / "modes" / "tower.json",
    *(
        ROOT / "config" / folder / path.name
        for folder, paths in {
            "disciples": sorted((ROOT / "config" / "disciples").glob("*.json")),
            "skills": sorted((ROOT / "config" / "skills").glob("*.json")),
            "bonds": sorted((ROOT / "config" / "bonds").glob("*.json")),
            "affixes": sorted((ROOT / "config" / "affixes").glob("*.json")),
            "enemies": sorted((ROOT / "config" / "enemies").glob("*.json")),
            "weapons": sorted((ROOT / "config" / "weapons").glob("*.json")),
            "recipes": sorted((ROOT / "config" / "recipes").glob("*.json")),
        }.items()
        for path in paths
    ),
    *(
        ROOT / path for path in (
            "backend/app/domain/battle.py",
            "backend/app/domain/run_engine.py",
            "backend/app/domain/progression.py",
            "backend/app/domain/recruit.py",
            "backend/app/domain/craft.py",
            "backend/app/domain/items.py",
            "backend/app/domain/weapons.py",
            "backend/app/domain/duty.py",
            "backend/app/domain/settle.py",
            "backend/app/domain/injuries.py",
            "backend/app/domain/affix.py",
            "backend/app/domain/rng.py",
            "backend/app/models/battle.py",
            "backend/app/models/save.py",
        )
    ),
)
TOOL_PATH = ROOT / "tools" / "measure_battles.py"


def _fingerprint(paths: tuple[Path, ...] | list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def input_fingerprint() -> str:
    """哈希覆盖战斗输入、执行代码与测量工具。"""
    return _fingerprint([*GAMEPLAY_PATHS, TOOL_PATH])


def gameplay_input_fingerprint() -> str:
    """哈希只覆盖战斗输入与执行代码，便于工具演进后对照。"""
    return _fingerprint(GAMEPLAY_PATHS)


def state_bytes(state: GameState) -> int:
    return len(state.model_dump_json().encode("utf-8"))


def choose_node_index(choices: list[RunNode], policy: str) -> int:
    """只使用玩家当前可见的节点类型，不预知后续路线。"""
    if policy == "defensive":
        for index, node in enumerate(choices):
            if node.kind == "battle":
                return index
    elif policy == "aggressive":
        for index, node in enumerate(choices):
            if node.kind in {"elite", "boss"}:
                return index
    return 0


AFFIX_GROUP_ORDER = {
    "defensive": ("jianshou", "qimou", "fengrui"),
    "aggressive": ("fengrui", "qimou", "jianshou"),
}
AFFIX_STAT_WEIGHTS = {
    "defensive": {"hp": 1.0, "def": 1.0, "shielding": .8, "healing": .6, "taken_damage": 1.2, "injury_recovery": .5},
    "aggressive": {"atk": 1.0, "spd": .6, "damage": 1.0},
}


def affix_score(affix: dict, policy: str) -> float:
    """按策略偏好给已展示词条打分：常驻效果按全额，条件效果打七折。

    条件道法需要队伍有对应触发源才生效，策略在只能看到候选时无法确认触发，
    因此按折扣计入，避免把"没有护盾的妙算"当成进攻首选。
    """
    weights = AFFIX_STAT_WEIGHTS.get(policy, {})
    score = sum(
        float(effect.get("value", 0)) * weights.get(effect.get("stat", ""), 0)
        for effect in affix.get("effects", [])
    )
    score += sum(
        float(value) * weights.get(key, 0)
        for key, value in (affix.get("bonuses") or {}).items()
    )
    for extra in affix.get("conditional") or []:
        score += 0.7 * sum(
            float(value) * weights.get(key, 0)
            for key, value in (extra.get("bonuses") or {}).items()
        )
    return score


def choose_affix_index(options: list[str], affix_pool: list[dict], policy: str) -> int:
    """按协同组偏好与已展示效果选择候选；真实候选同组时仍能区分。"""
    if policy == "first" or not options:
        return 0
    by_id = {affix["id"]: affix for affix in affix_pool}
    order = AFFIX_GROUP_ORDER.get(policy, ())
    best_group = next(
        (
            group for group in order
            if any(by_id.get(affix_id, {}).get("group") == group for affix_id in options)
        ),
        None,
    )
    candidates = [
        index for index, affix_id in enumerate(options)
        if best_group is None or by_id.get(affix_id, {}).get("group") == best_group
    ]
    if not candidates:
        return 0
    return max(
        candidates,
        key=lambda index: (affix_score(by_id.get(options[index], {}), policy), -index),
    )


def level_investment(level: int) -> dict[str, float]:
    """从 1 级升到目标等级的累计费用，复用真实升级费用函数。"""
    total = {"cultivation": 0.0, "spirit_stone": 0.0}
    for current in range(1, level):
        cost = upgrade_cost(DiscipleState(id="fixture", template_id="fixture", level=current))
        for key, value in cost.items():
            total[key] += value
    return total


def investment_for(
    party: tuple[str, ...], level: int, realm: int, templates: dict[str, dict],
) -> dict[str, object]:
    """按当前费用规则计算招募、等级和境界投入，不模拟资源获取。"""
    level_cost = level_investment(level)
    recruit = sum(
        templates[member].get("unlock_cost", {}).get("reputation", 0.0)
        for member in party
    )
    realm_cost = sum(
        templates[member].get("unlock_cost", {}).get("reputation", 0.0)
        * sum(REALM_UP_RATIOS.get(step, 0.0) for step in range(2, realm + 1))
        for member in party
    )
    return {
        "party_size": len(party),
        "recruit_reputation": round(recruit, 2),
        "level_upgrade": {
            "cultivation": round(level_cost["cultivation"] * len(party), 2),
            "spirit_stone": round(level_cost["spirit_stone"] * len(party), 2),
        },
        "realm_upgrade_reputation": round(realm_cost, 2),
        "growth_total": {
            "cultivation": round(level_cost["cultivation"] * len(party), 2),
            "spirit_stone": round(level_cost["spirit_stone"] * len(party), 2),
            "reputation": round(realm_cost, 2),
        },
        "ownership_and_growth_total_reputation": round(recruit + realm_cost, 2),
    }


def weapon_for_template(weapons: dict[str, dict], template_id: str) -> dict | None:
    """每名弟子最多一把专武，按模板反查配置。"""
    return next(
        (weapon for weapon in weapons.values() if weapon["template_id"] == template_id),
        None,
    )


def loadout_investment(
    party: tuple[str, ...], weapons: dict[str, dict], recipes: dict[str, dict],
    *, pills: bool = False, weapons_equipped: bool = False,
) -> dict[str, dict[str, int]]:
    """丹药取属性丹满次数，专武取对应弟子一把；材料按配置累加。"""
    pill_materials: Counter[str] = Counter()
    weapon_materials: Counter[str] = Counter()
    for member in party:
        if pills:
            for recipe_id in ATTRIBUTE_PILLS:
                for material_id, count in recipes[recipe_id]["inputs"].items():
                    pill_materials[material_id] += count * ATTRIBUTE_PILL_USES
        if not weapons_equipped:
            continue
        weapon = weapon_for_template(weapons, member)
        if weapon is None:
            continue
        for material_id, count in weapon["inputs"].items():
            weapon_materials[material_id] += count
    total: Counter[str] = pill_materials + weapon_materials
    return {
        "pill_materials": dict(sorted(pill_materials.items())),
        "weapon_materials": dict(sorted(weapon_materials.items())),
        "total_materials": dict(sorted(total.items())),
    }


def battle_metrics(battle: BattleSummary, floor: int) -> dict:
    """从服务端真实战报提取统计量，不重新计算伤害公式。"""
    sides = {unit.id: unit.side for unit in battle.final_units}
    damage_to_enemies = damage_to_allies = 0
    effective_healing = heal_effects = 0
    shield_to_allies = shield_to_enemies = 0
    absorbed_on_allies = absorbed_on_enemies = 0
    buff_effects = 0
    bond_triggers: Counter[str] = Counter()

    for event in battle.events:
        for bond in event.bonds:
            bond_triggers[bond] += 1
        for effect in event.effects:
            side = sides.get(effect.target_id)
            if effect.kind == "damage":
                if side == "enemy":
                    damage_to_enemies += effect.amount
                elif side == "ally":
                    damage_to_allies += effect.amount
                if side == "ally":
                    absorbed_on_allies += effect.absorbed
                elif side == "enemy":
                    absorbed_on_enemies += effect.absorbed
            elif effect.kind == "heal":
                effective_healing += effect.amount
                heal_effects += 1
            elif effect.kind == "shield":
                if side == "ally":
                    shield_to_allies += effect.amount
                elif side == "enemy":
                    shield_to_enemies += effect.amount
            elif effect.kind == "buff":
                buff_effects += 1

    allies = [unit for unit in battle.final_units if unit.side == "ally"]
    return {
        "floor": floor,
        "kind": battle.node.kind,
        "won": battle.won,
        "reason": battle.reason,
        "rounds": battle.rounds,
        "main_actions": len(battle.events),
        "effect_results": sum(len(event.effects) for event in battle.events),
        "damage_to_enemies": damage_to_enemies,
        "damage_to_allies": damage_to_allies,
        "effective_healing": effective_healing,
        "heal_effects": heal_effects,
        "heal_overflow": None,
        "shield_to_allies": shield_to_allies,
        "shield_to_enemies": shield_to_enemies,
        "shield_absorbed_on_allies": absorbed_on_allies,
        "shield_absorbed_on_enemies": absorbed_on_enemies,
        "shield_remaining_on_allies": sum(unit.shield for unit in allies),
        "ally_hp_after": sum(unit.hp for unit in allies),
        "ally_max_hp": sum(unit.max_hp for unit in allies),
        "survivors": sum(1 for unit in allies if unit.hp > 0),
        "party_size": len(allies),
        "buff_effects": buff_effects,
        "bond_triggers": dict(sorted(bond_triggers.items())),
    }


def _average(rows: list[dict], key: str) -> float:
    if not rows:
        return 0.0
    return round(sum(row[key] for row in rows) / len(rows), 4)


def summarize_encounters(encounters: list[dict]) -> dict:
    """按普通/精英/首领聚合单场统计。"""
    result: dict[str, dict] = {}
    for kind in ("battle", "elite", "boss"):
        rows = [row for row in encounters if row["kind"] == kind]
        if not rows:
            continue
        bonds: Counter[str] = Counter()
        for row in rows:
            bonds.update(row.get("bond_triggers", {}))
        result[kind] = {
            "count": len(rows),
            "wins": sum(1 for row in rows if row["won"]),
            "win_rate": round(sum(1 for row in rows if row["won"]) / len(rows), 4),
            "round_limit": sum(1 for row in rows if row["reason"] == "round_limit"),
            "rounds_total": sum(row["rounds"] for row in rows),
            "rounds_avg": _average(rows, "rounds"),
            "damage_to_enemies": sum(row["damage_to_enemies"] for row in rows),
            "damage_to_allies": sum(row["damage_to_allies"] for row in rows),
            "effective_healing": sum(row["effective_healing"] for row in rows),
            "shield_to_allies": sum(row["shield_to_allies"] for row in rows),
            "shield_absorbed_on_allies": sum(row["shield_absorbed_on_allies"] for row in rows),
            "survivors_avg": _average(rows, "survivors"),
            "bond_triggers": dict(sorted(bonds.items())),
        }
    return result


def summarize_cases(cases: list[dict]) -> list[dict]:
    """按阵容、档位与策略汇总三个种子的结果。"""
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for case in cases:
        key = (case["lineup"], case["tier"], case["policy"])
        groups.setdefault(key, []).append(case)

    summary = []
    for (lineup, tier, policy), rows in sorted(groups.items()):
        table = [encounter for case in rows for encounter in case["battles"]]
        bonds: Counter[str] = Counter()
        for case in rows:
            bonds.update(case["triggered_bonds"])
        summary.append({
            "lineup": lineup,
            "tier": tier,
            "policy": policy,
            "level": rows[0]["level"],
            "realm": rows[0]["realm"],
            "seeds": [case["seed"] for case in rows],
            "campaigns": len(rows),
            "clears": sum(1 for case in rows if case["termination"] == "cleared"),
            "defeats": sum(1 for case in rows if case["termination"] == "defeated"),
            "round_limit": sum(1 for case in rows if case["termination"] == "round_limit"),
            "clear_rate": round(
                sum(1 for case in rows if case["termination"] == "cleared") / len(rows), 4
            ),
            "avg_reached_floor": _average(rows, "reached_floor"),
            "avg_remaining_hp_ratio": _average(rows, "remaining_hp_ratio"),
            "avg_survivors": _average(rows, "survivors"),
            "avg_rounds": _average(rows, "rounds_total"),
            "avg_damage_to_enemies": _average(rows, "damage_to_enemies"),
            "avg_damage_to_allies": _average(rows, "damage_to_allies"),
            "avg_effective_healing": _average(rows, "effective_healing"),
            "avg_shield_to_allies": _average(rows, "shield_to_allies"),
            "avg_shield_absorbed_on_allies": _average(rows, "shield_absorbed_on_allies"),
            "avg_loot_cultivation": _average(rows, "loot_cultivation"),
            "avg_loot_spirit_stone": _average(rows, "loot_spirit_stone"),
            "avg_loot_reputation": _average(rows, "loot_reputation"),
            "bond_triggers": dict(sorted(bonds.items())),
            "investment": rows[0]["investment"],
            "encounter_summary": summarize_encounters(table),
        })
    return summary


def measure_campaign(
    lineup: str, party: tuple[str, ...], level: int, seed: int,
    policy: str = "first", realm: int = 1, tier: str | None = None,
    detailed: bool = False, pills: bool = False, weapon_loadout: bool = False,
) -> dict:
    """相同等级、境界、种子与策略下跑完出征，记录真实结果而非估算胜率。

    pills 表示每名弟子已服满三种属性丹中的攻击与防御上限；
    weapon_loadout 表示每名弟子已装备对应专武。两者都只影响出发快照。
    """
    if policy not in POLICIES:
        raise ValueError(f"未知策略：{policy}")
    templates, skills, bonds = load_disciples(), load_skills(), load_bonds()
    enemies, mode, affixes = load_enemies(), load_modes()["tower"], load_affixes()
    weapons, recipes = load_weapons(), load_recipes()
    state = GameState(
        resources=Resources(stamina=3),
        disciples=[
            DiscipleState(
                id=f"fixture_{index}", template_id=template_id,
                level=level, realm=realm,
                bonuses={"atk": .15, "def": .15} if pills else {},
                equipment=(
                    [weapon["id"]]
                    if weapon_loadout and (weapon := weapon_for_template(weapons, template_id))
                    else []
                ),
            )
            for index, template_id in enumerate(party)
        ],
        unlocks=list(party),
    )
    began = perf_counter()
    error = start_run(
        state, [disciple.id for disciple in state.disciples], templates, mode, NOW,
        seed=seed, bonds=bonds, skills=skills, enemies=enemies, affix_pool=affixes,
        weapons=weapons,
    )
    if error:
        raise RuntimeError(f"{lineup}: start_run: {error}")
    peak_bytes = state_bytes(state)
    battles: list[dict] = []
    decisions: list[dict] = []
    triggered: Counter[str] = Counter()
    for _ in range(mode["node_count"] * 2 + 2):
        run = state.active_run
        if run is None:
            raise RuntimeError("出征意外消失")
        status = run_status(run)
        if status in {"cleared", "defeated"}:
            break
        if status == "choosing_affix":
            index = choose_affix_index(run.affix_options, run.party_snapshot.affix_pool, policy)
            chosen = run.affix_options[index]
            group = next(
                (affix["group"] for affix in run.party_snapshot.affix_pool if affix["id"] == chosen),
                "",
            )
            decisions.append({
                "type": "affix", "after_floor": len(run.nodes),
                "options": list(run.affix_options), "chosen": chosen,
                "group": group, "index": index,
            })
            error = pick_affix(state, chosen)
        else:
            index = choose_node_index(run.choices, policy)
            node = run.choices[index]
            decisions.append({
                "type": "node", "floor": len(run.nodes) + 1,
                "options": [choice.kind for choice in run.choices],
                "chosen": node.kind, "index": index,
            })
            error = choose(state, index)
            if error is None:
                current = state.active_run
                battle = current.last_battle
                if battle is None:
                    raise RuntimeError("战斗结束却没有服务端战报")
                for event in battle.events:
                    triggered.update(event.bonds)
                record = {
                    "floor": len(current.nodes), "kind": battle.node.kind,
                    "won": battle.won, "reason": battle.reason,
                    "remaining_hp": current.hp, "rounds": battle.rounds,
                    "main_actions": len(battle.events),
                    "effect_results": sum(len(event.effects) for event in battle.events),
                    "triggered_bonds": sorted({
                        bond for event in battle.events for bond in event.bonds
                    }),
                }
                if detailed:
                    metrics = battle_metrics(battle, len(current.nodes))
                    record.update({
                        key: value for key, value in metrics.items()
                        if key not in {"bond_triggers", "remaining_hp"}
                    })
                    record["bond_triggers"] = metrics["bond_triggers"]
                    record["party_hp_after"] = current.hp
                battles.append(record)
        if error:
            raise RuntimeError(f"{lineup}: {status}: {error}")
        peak_bytes = max(peak_bytes, state_bytes(state))
    else:
        raise RuntimeError("出征超过预期节点决策次数")
    run = state.active_run
    if run is None:
        raise RuntimeError("出征意外消失")
    termination = run.end_reason or (
        "cleared" if len(run.nodes) >= run.party_snapshot.mode["node_count"] else "in_progress"
    )
    remaining_hp = run.hp
    max_hp = run.max_hp
    result = settle_run(state, mode, NOW)
    loot = result["loot"]
    elapsed_ms = (perf_counter() - began) * 1000
    record = {
        "lineup": lineup, "party": list(party),
        "rarities": [templates[member]["rarity"] for member in party],
        "level": level, "realm": realm, "seed": seed,
        "reached_floor": len(run.nodes),
        "won_battles": sum(battle["won"] for battle in battles),
        "victory": result["victory"], "remaining_hp": remaining_hp,
        "rounds_total": sum(battle["rounds"] for battle in battles),
        "main_actions_total": sum(battle["main_actions"] for battle in battles),
        "effect_results_total": sum(battle["effect_results"] for battle in battles),
        "triggered_bonds": dict(sorted(triggered.items())),
        "peak_state_json_bytes": peak_bytes,
        "settled_state_json_bytes": state_bytes(state),
        "wall_ms": round(elapsed_ms, 3), "battles": battles,
    }
    if detailed:
        encounters = [battle for battle in battles if "damage_to_enemies" in battle]
        record.update({
            "tier": tier,
            "policy": policy,
            "termination": termination,
            "remaining_hp_ratio": round(remaining_hp / max_hp, 4) if max_hp else 0.0,
            "survivors": sum(1 for hp in run.member_hp.values() if hp > 0),
            "party_size": len(party),
            "rng_cursor": run.rng_cursor,
            "damage_to_enemies": sum(battle["damage_to_enemies"] for battle in encounters),
            "damage_to_allies": sum(battle["damage_to_allies"] for battle in encounters),
            "effective_healing": sum(battle["effective_healing"] for battle in encounters),
            "heal_effects": sum(battle["heal_effects"] for battle in encounters),
            "heal_overflow": None,
            "shield_to_allies": sum(battle["shield_to_allies"] for battle in encounters),
            "shield_absorbed_on_allies": sum(
                battle["shield_absorbed_on_allies"] for battle in encounters
            ),
            "buff_effects": sum(battle["buff_effects"] for battle in encounters),
            "investment": investment_for(party, level, realm, templates),
            "loadout": {"pills": pills, "weapons": weapon_loadout},
            "equipment_investment": loadout_investment(
                party, weapons, recipes,
                pills=pills, weapons_equipped=weapon_loadout,
            ),
            "loot": loot,
            "loot_cultivation": round(float(loot.get("cultivation", 0)), 2),
            "loot_spirit_stone": round(float(loot.get("spirit_stone", 0)), 2),
            "loot_reputation": round(float(loot.get("reputation", 0)), 2),
            "decisions": decisions,
            "encounter_summary": summarize_encounters(encounters),
        })
    return record


def measure_full_round_fixture(repetitions: int) -> dict:
    """人工高气血低伤害场景，保证 6v6 全员存活至第 20 回合。

    该场景仅测主行动上限及战报体积；其属性不属于正式游戏平衡。
    """
    active = SkillDefinition(
        id="fixture_active", name="压力场景施法", type="active", cooldown=3,
        actions=[
            BattleAction(kind="damage", target="all_enemies", count=6, coefficient=.1),
            BattleAction(kind="heal", target="all_allies", count=6, coefficient=.1),
            BattleAction(kind="shield", target="all_allies", count=6, coefficient=.1),
            BattleAction(kind="buff", target="all_allies", count=6, stat="def", value=.1),
        ],
    )
    passive = SkillDefinition(id="fixture_passive", name="压力场景被动", type="passive", bonuses={"shielding": .1})
    units = [BattleUnit(
        id=f"fixture_{side}_{slot}", template_id="artificial_fixture", name=f"{side}_{slot}",
        slot=slot, attack=1, defense=1, health=100_000, speed=10,
        active=active, passive=passive,
    ) for side in ("ally", "enemy") for slot in range(6)]
    durations = []
    outcome = None
    for _ in range(repetitions):
        began = perf_counter()
        outcome = simulate_battle(units[:6], units[6:], {}, [])
        durations.append((perf_counter() - began) * 1000)
    expected = 12 * ROUND_LIMIT
    if outcome.rounds != ROUND_LIMIT or len(outcome.events) != expected:
        raise RuntimeError("人工压力场景没有达到 6v6 全回合主行动上限")
    report = {
        "initial_units": [unit.model_dump(mode="json") for unit in outcome.initial_units],
        "final_units": [unit.model_dump(mode="json") for unit in outcome.final_units],
        "events": [event.model_dump(mode="json") for event in outcome.events],
    }
    fixture_state = GameState(active_run=ActiveRun(
        run_seed=0, started_at=NOW, party=[unit.id for unit in units[:6]],
        hp=sum(unit.hp for unit in outcome.final_units if unit.side == "ally"),
        max_hp=sum(unit.health for unit in units[:6]),
        member_hp={unit.id: unit.hp for unit in outcome.final_units if unit.side == "ally"},
        end_reason=outcome.reason,
        party_snapshot=RunPartySnapshot(combatants=tuple(units[:6])),
        last_battle=BattleSummary(
            id="artificial_fixture", party_power=0, enemy_power=0,
            hp_before=sum(unit.health for unit in units[:6]),
            hp_after=sum(unit.hp for unit in outcome.final_units if unit.side == "ally"),
            damage=0, won=outcome.won, node=RunNode(kind="fixture", enemy="artificial_fixture", power=0),
            rounds=outcome.rounds, reason=outcome.reason,
            initial_units=outcome.initial_units, final_units=outcome.final_units, events=outcome.events,
        ),
    ))
    return {
        "fixture": "artificial_high_hp_low_damage_6v6",
        "purpose": "Maximum main-action count; not a real lineup balance sample or an exhaustive worst-case log-size bound.",
        "rounds": outcome.rounds, "reason": outcome.reason,
        "main_action_limit": expected, "main_actions": len(outcome.events),
        "effect_results": sum(len(event.effects) for event in outcome.events),
        "serialized_battle_report_bytes": len(json.dumps(report, ensure_ascii=False, separators=(",", ":")).encode("utf-8")),
        "state_json_bytes": state_bytes(fixture_state),
        "repetitions": repetitions, "wall_ms": [round(value, 3) for value in durations],
        "median_wall_ms": round(statistics.median(durations), 3),
    }


def load_t16_reference(path: Path) -> dict:
    if not path.exists():
        return {"available": False, "path": str(path)}
    reference = json.loads(path.read_text(encoding="utf-8"))
    return {
        "available": True,
        "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "input_sha256": reference.get("input_sha256"),
        "case_count": len(reference.get("campaigns", [])),
        "method": reference.get("method", {}),
    }


def compare_t16_reference(cases: list[dict], path: Path) -> dict:
    """比较 T17 的早期/中期、首项策略样本与 T16 历史结果。"""
    reference = load_t16_reference(path)
    if not reference["available"]:
        return reference
    historical = json.loads(path.read_text(encoding="utf-8"))
    old_cases = {
        (case["lineup"], case["level"], case["seed"]): case
        for case in historical.get("campaigns", [])
    }
    new_cases = {
        (case["lineup"], case["level"], case["seed"]): case
        for case in cases
        if case["policy"] == "first" and case["realm"] == 1 and case["level"] in LEVELS
    }
    keys = (
        "reached_floor", "won_battles", "victory", "remaining_hp",
        "rounds_total", "main_actions_total", "effect_results_total", "triggered_bonds",
    )
    differences = []
    for key in sorted(old_cases):
        old, new = old_cases[key], new_cases.get(key)
        if new is None:
            differences.append({"case": key, "fields": {"missing_in_t17": True}})
            continue
        changed = {
            field: [old.get(field), new.get(field)]
            for field in keys if old.get(field) != new.get(field)
        }
        if changed:
            differences.append({"case": key, "fields": changed})
    return {
        **reference,
        "compared_field_names": list(keys),
        "matched_cases": len(old_cases) - len(differences),
        "different_cases": len(differences),
        "differences": differences,
        "notes": "Wall time and T17-only detailed metrics are excluded from comparison.",
    }


def compare_t17_reference(cases: list[dict], path: Path) -> dict:
    """比较 T18 合法档位与 T17 重叠档位；T17 6/1 是旧档超限，不参与。"""
    if not path.exists():
        return {"available": False, "path": str(path)}
    reference = json.loads(path.read_text(encoding="utf-8"))
    compared_tiers = {"early_l1_r1", "mid_l3_r1", "late_l6_r2"}
    old_cases = {
        (case["lineup"], case["level"], case["realm"], case["policy"], case["seed"]): case
        for case in reference.get("cases", [])
        if case.get("tier") in compared_tiers
    }
    new_cases = {
        (case["lineup"], case["level"], case["realm"], case["policy"], case["seed"]): case
        for case in cases
        if case["tier"] in compared_tiers
    }
    keys = (
        "termination", "reached_floor", "victory", "remaining_hp", "remaining_hp_ratio",
        "survivors", "rounds_total", "main_actions_total", "effect_results_total",
        "triggered_bonds", "damage_to_enemies", "damage_to_allies", "effective_healing",
        "shield_to_allies", "shield_absorbed_on_allies",
    )
    differences = []
    for key in sorted(old_cases):
        old, new = old_cases[key], new_cases.get(key)
        if new is None:
            differences.append({"case": key, "fields": {"missing_in_t18": True}})
            continue
        changed = {
            field: [old.get(field), new.get(field)]
            for field in keys if old.get(field) != new.get(field)
        }
        if changed:
            differences.append({"case": key, "fields": changed})
    return {
        "available": True,
        "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "input_sha256": reference.get("input_sha256"),
        "case_count": len(reference.get("cases", [])),
        "compared_cases": len(old_cases),
        "compared_tiers": sorted(compared_tiers),
        "matched_cases": len(old_cases) - len(differences),
        "different_cases": len(differences),
        "differences": differences,
        "notes": "T17 6/1 is a legacy over-cap tier and is excluded; 10/3 is new in T18.",
    }


def compare_t18_reference(cases: list[dict], path: Path) -> dict:
    """T19 对照组只比较 T18 已有的 3/1、6/2 与首项策略。"""
    if not path.exists():
        return {"available": False, "path": str(path)}
    reference = json.loads(path.read_text(encoding="utf-8"))
    compared_tiers = {"mid_l3_r1", "late_l6_r2"}
    old_cases = {
        (case["lineup"], case["level"], case["realm"], case["policy"], case["seed"]): case
        for case in reference.get("cases", [])
        if case.get("tier") in compared_tiers and case.get("policy") == "first"
    }
    new_cases = {
        (case["lineup"], case["level"], case["realm"], case["policy"], case["seed"]): case
        for case in cases
        if case["tier"] in compared_tiers and case["policy"] == "first"
        and case["loadout"] == {"pills": False, "weapons": False}
    }
    keys = (
        "termination", "reached_floor", "victory", "remaining_hp", "remaining_hp_ratio",
        "survivors", "rounds_total", "main_actions_total", "effect_results_total",
        "triggered_bonds", "damage_to_enemies", "damage_to_allies", "effective_healing",
        "shield_to_allies", "shield_absorbed_on_allies", "rng_cursor", "decisions",
    )
    differences = []
    for key in sorted(old_cases):
        old, new = old_cases[key], new_cases.get(key)
        if new is None:
            differences.append({"case": key, "fields": {"missing_in_t19": True}})
            continue
        changed = {
            field: [old.get(field), new.get(field)]
            for field in keys if old.get(field) != new.get(field)
        }
        if changed:
            differences.append({"case": key, "fields": changed})
    return {
        "available": True,
        "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "input_sha256": reference.get("input_sha256"),
        "case_count": len(reference.get("cases", [])),
        "compared_cases": len(old_cases),
        "compared_tiers": sorted(compared_tiers),
        "compared_policy": "first",
        "matched_cases": len(old_cases) - len(differences),
        "different_cases": len(differences),
        "differences": differences,
        "notes": "Only the no-pill/no-weapon control is compared; 10/3 and other policies are new in T19.",
    }


def loadout_name(case: dict) -> str:
    """把布尔投入组合折算成稳定名称。"""
    loadout = case["loadout"]
    return "both" if loadout["pills"] and loadout["weapons"] else (
        "pills" if loadout["pills"] else "weapons" if loadout["weapons"] else "control"
    )


def summarize_loadout_cases(cases: list[dict]) -> list[dict]:
    """按阵容、档位与投入方式汇总，并给出相对无投入对照的差值。"""
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for case in cases:
        groups.setdefault(
            (case["lineup"], case["tier"], loadout_name(case)), [],
        ).append(case)

    summary = []
    for (lineup, tier, loadout), rows in sorted(groups.items()):
        table = [encounter for case in rows for encounter in case["battles"]]
        entry = {
            "lineup": lineup, "tier": tier, "loadout": loadout,
            "level": rows[0]["level"], "realm": rows[0]["realm"],
            "seeds": [case["seed"] for case in rows],
            "campaigns": len(rows),
            "clears": sum(1 for case in rows if case["termination"] == "cleared"),
            "defeats": sum(1 for case in rows if case["termination"] == "defeated"),
            "clear_rate": round(
                sum(1 for case in rows if case["termination"] == "cleared") / len(rows), 4
            ),
            "avg_reached_floor": _average(rows, "reached_floor"),
            "avg_remaining_hp_ratio": _average(rows, "remaining_hp_ratio"),
            "avg_survivors": _average(rows, "survivors"),
            "avg_rounds": _average(rows, "rounds_total"),
            "avg_damage_to_enemies": _average(rows, "damage_to_enemies"),
            "avg_damage_to_allies": _average(rows, "damage_to_allies"),
            "avg_effective_healing": _average(rows, "effective_healing"),
            "avg_shield_to_allies": _average(rows, "shield_to_allies"),
            "equipment_investment": rows[0]["equipment_investment"],
            "encounter_summary": summarize_encounters(table),
        }
        summary.append(entry)

    controls = {
        (entry["lineup"], entry["tier"]): entry
        for entry in summary if entry["loadout"] == "control"
    }
    delta_keys = (
        "clear_rate", "avg_reached_floor", "avg_remaining_hp_ratio", "avg_survivors",
        "avg_rounds", "avg_damage_to_enemies", "avg_damage_to_allies",
        "avg_effective_healing", "avg_shield_to_allies",
    )
    for entry in summary:
        if entry["loadout"] == "control":
            entry["delta_vs_control"] = {}
            continue
        control = controls[(entry["lineup"], entry["tier"])]
        entry["delta_vs_control"] = {
            key: round(entry[key] - control[key], 4) for key in delta_keys
        }
    return summary


def compare_t19_reference(cases: list[dict], path: Path) -> dict:
    """T20 与 T19 的重叠档位/投入逐项对照，差异是敌人改动本身造成的。"""
    if not path.exists():
        return {"available": False, "path": str(path)}
    reference = json.loads(path.read_text(encoding="utf-8"))
    tiers = ("mid_l3_r1", "late_l6_r2", "end_l10_r3")
    loadouts = ("control", "pills", "weapons", "both")

    def key(case: dict) -> tuple[str, str, int, str]:
        return case["lineup"], case["tier"], case["seed"], loadout_name(case)

    old_cases = {key(case): case for case in reference.get("cases", [])}
    new_cases = {key(case): case for case in cases}
    compared = [item for item in old_cases if item[1] in tiers and item in new_cases]
    fields = (
        "termination", "reached_floor", "remaining_hp_ratio", "rounds_total",
        "damage_to_enemies", "damage_to_allies", "effective_healing", "survivors",
    )
    differences = []
    for item in sorted(compared):
        old, new = old_cases[item], new_cases[item]
        changed = {field: [old.get(field), new.get(field)] for field in fields if old.get(field) != new.get(field)}
        if changed:
            differences.append({"case": item, "fields": changed})

    def rate(rows: list[dict], termination: str) -> float:
        return round(sum(1 for row in rows if row["termination"] == termination) / len(rows), 4)

    aggregate = []
    for tier in tiers:
        for loadout in loadouts:
            old_rows = [
                case for case in reference.get("cases", [])
                if case["tier"] == tier and loadout_name(case) == loadout
            ]
            new_rows = [
                case for case in cases
                if case["tier"] == tier and loadout_name(case) == loadout
            ]
            if not old_rows or not new_rows:
                continue
            entry = {
                "tier": tier, "loadout": loadout,
                "old_cases": len(old_rows), "new_cases": len(new_rows),
            }
            for label, rows in (("old", old_rows), ("new", new_rows)):
                entry[f"{label}_clear_rate"] = rate(rows, "cleared")
                entry[f"{label}_round_limit_rate"] = rate(rows, "round_limit")
                for field, name in (
                    ("reached_floor", "avg_reached_floor"),
                    ("remaining_hp_ratio", "avg_remaining_hp_ratio"),
                    ("rounds_total", "avg_rounds"),
                    ("damage_to_allies", "avg_damage_to_allies"),
                    ("effective_healing", "avg_effective_healing"),
                ):
                    entry[f"{label}_{name}"] = _average(rows, field)
            for name in (
                "clear_rate", "round_limit_rate", "avg_reached_floor",
                "avg_remaining_hp_ratio", "avg_rounds", "avg_damage_to_allies",
                "avg_effective_healing",
            ):
                entry[f"delta_{name}"] = round(entry[f"new_{name}"] - entry[f"old_{name}"], 4)
            aggregate.append(entry)
    return {
        "available": True,
        "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "input_sha256": reference.get("input_sha256"),
        "compared_cases": len(compared),
        "matched_cases": len(compared) - len(differences),
        "different_cases": len(differences),
        "aggregate": aggregate,
        "notes": (
            "T20 intentionally changes enemies; differences are the measured effect of the new "
            "skills, compositions, elite/boss multipliers and passives, not a reproducibility failure."
        ),
    }


def run_t16_suite(repetitions: int) -> dict:
    fingerprint = input_fingerprint()
    campaigns = [
        measure_campaign(name, party, level, seed)
        for name, party in LINEUPS.items() for level in LEVELS for seed in SEEDS
    ]
    fixture = measure_full_round_fixture(repetitions)
    if fingerprint != input_fingerprint():
        raise RuntimeError("测量期间输入文件改变，请在修改稳定后重新运行")
    return {
        "format_version": 1, "input_sha256": fingerprint,
        "command": "backend/.venv/Scripts/python.exe tools/measure_battles.py --suite t16 --output artifacts/t17/t16-rerun.json",
        "environment": {
            "python": platform.python_version(), "platform": platform.system(),
            "architecture": platform.machine(),
        },
        "method": {
            "storage": "in-memory GameState only; no database access",
            "seeds": list(SEEDS), "levels": list(LEVELS), "realm": 1,
            "policy": "Always choose route index 0 and affix option index 0.",
            "notes": "36 deterministic campaign observations, not a probability estimate. Timing includes simulation and state serialization; no front-end playback or network.",
            "substitution": "mechanics_core: replace rarity-3 Yue Fei/Zhao Yun with rarity-1 Du Fu/Jing Wei; keep the other four members and their order.",
        },
        "campaigns": campaigns, "full_round_fixture": fixture,
    }


def run_t17_suite(repetitions: int, t16_reference_path: Path) -> dict:
    fingerprint = input_fingerprint()
    gameplay_fingerprint = gameplay_input_fingerprint()
    cases = [
        measure_campaign(
            name, party, level, seed, policy=policy, realm=realm, tier=tier, detailed=True,
        )
        for name, party in LINEUPS.items()
        for tier, (level, realm) in T17_TIERS.items()
        for policy in POLICIES
        for seed in SEEDS
    ]
    fixture = measure_full_round_fixture(repetitions)
    if fingerprint != input_fingerprint() or gameplay_fingerprint != gameplay_input_fingerprint():
        raise RuntimeError("测量期间输入文件改变，请在修改稳定后重新运行")
    reference = compare_t16_reference(cases, t16_reference_path)
    return {
        "format_version": 2,
        "suite": "t17",
        "input_sha256": fingerprint,
        "gameplay_input_sha256": gameplay_fingerprint,
        "command": "backend/.venv/Scripts/python.exe tools/measure_battles.py --suite t17",
        "environment": {
            "python": platform.python_version(), "platform": platform.system(),
            "architecture": platform.machine(),
        },
        "method": {
            "storage": "in-memory GameState only; no database access",
            "seeds": list(SEEDS),
            "tiers": {name: {"level": level, "realm": realm} for name, (level, realm) in T17_TIERS.items()},
            "policies": POLICY_DESCRIPTIONS,
            "policy": "Node and affix choices use only the options visible at that decision; no future route knowledge.",
            "notes": (
                f"{len(cases)} deterministic campaign observations across "
                f"{len(LINEUPS)} lineups, {len(T17_TIERS)} tiers, {len(POLICIES)} policies and "
                f"{len(SEEDS)} seeds. Not a probability estimate. Timing includes simulation and "
                "state serialization; no front-end playback or network."
            ),
            "metrics": {
                "damage_to_enemies": "sum of final HP damage dealt to enemies, after shields",
                "damage_to_allies": "sum of final HP damage taken by allies, after shields",
                "effective_healing": "sum of actual heal amounts applied",
                "shield_to_allies": "sum of actual shield increments applied to allies",
                "shield_absorbed_on_allies": "sum of damage absorbed by ally shields",
                "bond_triggers": "count of battle events listing each named bond",
                "investment": "actual upgrade costs plus recruit and 50% realm-up reputation costs",
            },
            "unavailable_metrics": [
                "heal_overflow: battle report stores effective heal only; not filled with zero",
            ],
            "substitution": "mechanics_core: replace rarity-3 Yue Fei/Zhao Yun with rarity-1 Du Fu/Jing Wei; keep the other four members and their order.",
        },
        "reference": reference,
        "cases": cases,
        "summary": summarize_cases(cases),
        "encounter_summary_by_kind": summarize_encounters(
            [encounter for case in cases for encounter in case["battles"]]
        ),
        "full_round_fixture": fixture,
    }


def run_t18_suite(repetitions: int, t17_reference_path: Path) -> dict:
    fingerprint = input_fingerprint()
    gameplay_fingerprint = gameplay_input_fingerprint()
    cases = [
        measure_campaign(
            name, party, level, seed, policy=policy, realm=realm, tier=tier, detailed=True,
        )
        for name, party in LINEUPS.items()
        for tier, (level, realm) in T18_TIERS.items()
        for policy in POLICIES
        for seed in SEEDS
    ]
    fixture = measure_full_round_fixture(repetitions)
    if fingerprint != input_fingerprint() or gameplay_fingerprint != gameplay_input_fingerprint():
        raise RuntimeError("测量期间输入文件改变，请在修改稳定后重新运行")
    reference = compare_t17_reference(cases, t17_reference_path)
    return {
        "format_version": 3,
        "suite": "t18",
        "input_sha256": fingerprint,
        "gameplay_input_sha256": gameplay_fingerprint,
        "command": "backend/.venv/Scripts/python.exe tools/measure_battles.py --suite t18",
        "environment": {
            "python": platform.python_version(), "platform": platform.system(),
            "architecture": platform.machine(),
        },
        "method": {
            "storage": "in-memory GameState only; no database access",
            "seeds": list(SEEDS),
            "tiers": {name: {"level": level, "realm": realm} for name, (level, realm) in T18_TIERS.items()},
            "policies": POLICY_DESCRIPTIONS,
            "policy": "Node and affix choices use only the options visible at that decision; no future route knowledge.",
            "notes": (
                f"{len(cases)} deterministic campaign observations across "
                f"{len(LINEUPS)} lineups, {len(T18_TIERS)} legal T18 tiers, "
                f"{len(POLICIES)} policies and {len(SEEDS)} seeds. T17 6/1 is a legacy "
                "over-cap control and is not a target. 10/3 is the new end tier."
            ),
            "metrics": {
                "damage_to_enemies": "sum of final HP damage dealt to enemies, after shields",
                "damage_to_allies": "sum of final HP damage taken by allies, after shields",
                "effective_healing": "sum of actual heal amounts applied",
                "shield_to_allies": "sum of actual shield increments applied to allies",
                "shield_absorbed_on_allies": "sum of damage absorbed by ally shields",
                "bond_triggers": "count of battle events listing each named bond",
                "investment": "actual upgrade costs plus recruit and per-realm 0.5/0.75 reputation ratios",
            },
            "unavailable_metrics": [
                "heal_overflow: battle report stores effective heal only; not filled with zero",
            ],
            "substitution": "mechanics_core: replace rarity-3 Yue Fei/Zhao Yun with rarity-1 Du Fu/Jing Wei; keep the other four members and their order.",
        },
        "reference": reference,
        "cases": cases,
        "summary": summarize_cases(cases),
        "encounter_summary_by_kind": summarize_encounters(
            [encounter for case in cases for encounter in case["battles"]]
        ),
        "full_round_fixture": fixture,
    }


def run_t19_suite(repetitions: int, t18_reference_path: Path) -> dict:
    fingerprint = input_fingerprint()
    gameplay_fingerprint = gameplay_input_fingerprint()
    cases = [
        measure_campaign(
            name, party, level, seed, policy="first", realm=realm, tier=tier, detailed=True,
            pills=pills, weapon_loadout=weapons,
        )
        for name, party in LINEUPS.items()
        for tier, (level, realm) in T19_TIERS.items()
        for pills, weapons in T19_LOADOUTS.values()
        for seed in SEEDS
    ]
    fixture = measure_full_round_fixture(repetitions)
    if fingerprint != input_fingerprint() or gameplay_fingerprint != gameplay_input_fingerprint():
        raise RuntimeError("测量期间输入文件改变，请在修改稳定后重新运行")
    reference = compare_t18_reference(cases, t18_reference_path)
    return {
        "format_version": 4,
        "suite": "t19",
        "input_sha256": fingerprint,
        "gameplay_input_sha256": gameplay_fingerprint,
        "command": "backend/.venv/Scripts/python.exe tools/measure_battles.py --suite t19",
        "environment": {
            "python": platform.python_version(), "platform": platform.system(),
            "architecture": platform.machine(),
        },
        "method": {
            "storage": "in-memory GameState only; no database access",
            "seeds": list(SEEDS),
            "tiers": {name: {"level": level, "realm": realm} for name, (level, realm) in T19_TIERS.items()},
            "loadouts": {
                "control": "no attribute pills and no exclusive weapon",
                "pills": "each disciple has 3 uses of both attack and defense attribute pills (+15% each)",
                "weapons": "each disciple equips their own exclusive weapon",
                "both": "full attribute pills plus exclusive weapons",
            },
            "policy": "Always choose route index 0 and affix option index 0, matching the T16 baseline.",
            "notes": (
                f"{len(cases)} deterministic campaign observations across "
                f"{len(LINEUPS)} lineups, {len(T19_TIERS)} legal tiers, "
                f"{len(T19_LOADOUTS)} loadouts and {len(SEEDS)} seeds. "
                "Not a probability estimate. Investment materials are reported separately from "
                "cultivation/spirit-stone growth costs; production pills and production weapons "
                "are excluded because they do not change battle inputs."
            ),
            "metrics": {
                "equipment_investment": "material counts for 3 uses of both attribute pills and one matching weapon per disciple",
                "delta_vs_control": "loadout average minus the same lineup/tier control average",
            },
            "unavailable_metrics": [
                "heal_overflow: battle report stores effective heal only; not filled with zero",
            ],
            "substitution": "mechanics_core: replace rarity-3 Yue Fei/Zhao Yun with rarity-1 Du Fu/Jing Wei; keep the other four members and their order.",
        },
        "reference": reference,
        "cases": cases,
        "summary": summarize_loadout_cases(cases),
        "encounter_summary_by_kind": summarize_encounters(
            [encounter for case in cases for encounter in case["battles"]]
        ),
        "full_round_fixture": fixture,
    }


def run_t20_suite(repetitions: int, t19_reference_path: Path) -> dict:
    fingerprint = input_fingerprint()
    gameplay_fingerprint = gameplay_input_fingerprint()
    cases = [
        measure_campaign(
            name, party, level, seed, policy="first", realm=realm, tier=tier, detailed=True,
            pills=pills, weapon_loadout=weapons,
        )
        for name, party in LINEUPS.items()
        for tier, (level, realm) in T18_TIERS.items()
        for pills, weapons in T19_LOADOUTS.values()
        for seed in SEEDS
    ]
    fixture = measure_full_round_fixture(repetitions)
    if fingerprint != input_fingerprint() or gameplay_fingerprint != gameplay_input_fingerprint():
        raise RuntimeError("测量期间输入文件改变，请在修改稳定后重新运行")
    reference = compare_t19_reference(cases, t19_reference_path)
    return {
        "format_version": 5,
        "suite": "t20",
        "input_sha256": fingerprint,
        "gameplay_input_sha256": gameplay_fingerprint,
        "command": "backend/.venv/Scripts/python.exe tools/measure_battles.py --suite t20",
        "environment": {
            "python": platform.python_version(), "platform": platform.system(),
            "architecture": platform.machine(),
        },
        "method": {
            "storage": "in-memory GameState only; no database access",
            "seeds": list(SEEDS),
            "tiers": {name: {"level": level, "realm": realm} for name, (level, realm) in T18_TIERS.items()},
            "loadouts": {
                "control": "no attribute pills and no exclusive weapon",
                "pills": "each disciple has 3 uses of both attack and defense attribute pills (+15% each)",
                "weapons": "each disciple equips their own exclusive weapon",
                "both": "full attribute pills plus exclusive weapons",
            },
            "policy": "Always choose route index 0 and affix option index 0, matching T16/T19.",
            "notes": (
                f"{len(cases)} deterministic campaign observations across "
                f"{len(LINEUPS)} lineups, {len(T18_TIERS)} legal tiers, "
                f"{len(T19_LOADOUTS)} loadouts and {len(SEEDS)} seeds. "
                "T20 changes enemy skills, compositions and elite/boss coefficients; the control and "
                "loadout columns are compared with T19 on overlapping tiers."
            ),
            "metrics": {
                "equipment_investment": "material counts for 3 uses of both attribute pills and one matching weapon per disciple",
                "delta_vs_control": "loadout average minus the same lineup/tier control average",
                "reference_aggregate": "T20 vs T19 average by tier/loadout; differences are intended enemy changes",
            },
            "unavailable_metrics": [
                "heal_overflow: battle report stores effective heal only; not filled with zero",
            ],
            "substitution": "mechanics_core: replace rarity-3 Yue Fei/Zhao Yun with rarity-1 Du Fu/Jing Wei; keep the other four members and their order.",
        },
        "reference": reference,
        "cases": cases,
        "summary": summarize_loadout_cases(cases),
        "encounter_summary_by_kind": summarize_encounters(
            [encounter for case in cases for encounter in case["battles"]]
        ),
        "full_round_fixture": fixture,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("t16", "t17", "t18", "t19", "t20"), default="t16")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--repetitions", type=int, default=5, help="人工满回合场景测量次数，默认5")
    parser.add_argument(
        "--t16-reference", type=Path, default=ROOT / "artifacts" / "t16" / "benchmark.json",
        help="T17 对照使用的 T16 历史结果",
    )
    parser.add_argument(
        "--t17-reference", type=Path, default=ROOT / "artifacts" / "t17" / "baseline.json",
        help="T18 对照使用的 T17 历史结果",
    )
    parser.add_argument(
        "--t18-reference", type=Path, default=ROOT / "artifacts" / "t18" / "baseline.json",
        help="T19 对照使用的 T18 历史结果",
    )
    parser.add_argument(
        "--t19-reference", type=Path, default=ROOT / "artifacts" / "t19" / "baseline.json",
        help="T20 对照使用的 T19 历史结果",
    )
    args = parser.parse_args(argv)
    if MAX_PARTY != 6 or not 1 <= args.repetitions <= 20:
        parser.error("需要已接入的六人战斗引擎，repetitions 必须是1..20")
    output = args.output or (
        ROOT / "artifacts" / "t17" / "t16-rerun.json"
        if args.suite == "t16"
        else ROOT / "artifacts" / "t17" / "baseline.json"
        if args.suite == "t17"
        else ROOT / "artifacts" / "t18" / "baseline.json"
        if args.suite == "t18"
        else ROOT / "artifacts" / "t19" / "baseline.json"
        if args.suite == "t19"
        else ROOT / "artifacts" / "t20" / "baseline.json"
    )
    if args.suite == "t16":
        report = run_t16_suite(args.repetitions)
    elif args.suite == "t17":
        report = run_t17_suite(args.repetitions, args.t16_reference)
    elif args.suite == "t18":
        report = run_t18_suite(args.repetitions, args.t17_reference)
    elif args.suite == "t19":
        report = run_t19_suite(args.repetitions, args.t18_reference)
    else:
        report = run_t20_suite(args.repetitions, args.t19_reference)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.suite == "t16":
        print(json.dumps({
            "suite": "t16", "campaigns": len(report["campaigns"]),
            "input_sha256": report["input_sha256"],
            "fixture_main_actions": report["full_round_fixture"]["main_actions"],
            "fixture_median_wall_ms": report["full_round_fixture"]["median_wall_ms"],
            "max_campaign_state_json_bytes": max(
                case["peak_state_json_bytes"] for case in report["campaigns"]
            ),
            "output": str(output),
        }))
    else:
        print(json.dumps({
            "suite": args.suite, "cases": len(report["cases"]),
            "summary_groups": len(report["summary"]),
            "input_sha256": report["input_sha256"],
            "gameplay_input_sha256": report["gameplay_input_sha256"],
            "reference_matched": report["reference"].get("matched_cases"),
            "reference_different": report["reference"].get("different_cases"),
            "fixture_main_actions": report["full_round_fixture"]["main_actions"],
            "fixture_median_wall_ms": report["full_round_fixture"]["median_wall_ms"],
            "output": str(output),
        }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
