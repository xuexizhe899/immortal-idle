#!/usr/bin/env python3
"""T22 路线版本与固定政策对照，在内存中调用正式出征流程。

运行：backend/.venv/Scripts/python.exe tools/measure_routes.py
只读配置，不连接数据库。命令数不是 UI 点击数，计算耗时不是实玩时长。
新旧路线版本消费的 RNG 不同，相同起点结果差异不能解释成单变量因果。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config_loader import (  # noqa: E402
    load_affixes, load_bonds, load_disciples, load_enemies, load_modes, load_skills, load_weapons,
)
from app.domain.run_engine import (  # noqa: E402
    choose, encounter_roster, pick_affix, run_status, settle_run, start_run,
)
from app.models.save import GameState, DiscipleState, Resources  # noqa: E402
from measure_battles import battle_metrics, gameplay_input_fingerprint  # noqa: E402

NOW = datetime(2026, 11, 14, 0, 0, tzinfo=timezone.utc)
SEEDS = (17, 2026, 11012)
TIERS = {"mid_l3_r1": (3, 1), "late_l6_r2": (6, 2)}
LINEUPS = {
    "wuhu_benyue": ("guanyu", "zhangfei", "zhaoyun", "houyi", "change", "huatuo"),
    "highest_rarity": ("guanyu", "nezha", "yangjian", "yuefei", "zhaoyun", "zhugeliang"),
}
POLICIES = ("first", "low_power", "high_reward")
FORK_FLOORS = (9, 13, 17)


def select_route(options: list[dict], policy: str) -> int:
    """固定政策只看当前可见候选，平局保留首项，不读取战斗结果。"""
    if policy == "first":
        return 0
    if policy == "low_power":
        return min(range(len(options)), key=lambda index: (options[index]["power"], index))
    if policy == "high_reward":
        return max(range(len(options)), key=lambda index: (options[index]["reward"].get("cultivation", 0), -index))
    raise ValueError(f"未知路线政策：{policy}")


def visible_options(state: GameState) -> list[dict]:
    """旧局编成按固化模式与当前层解析；新局直接使用已保存的候选。"""
    run = state.active_run
    return [
        {
            **node.model_dump(),
            "enemies": list(node.enemies or encounter_roster(run.party_snapshot.mode, node.kind, len(run.nodes))),
        }
        for node in run.choices
    ]


def option_key(option: dict) -> str:
    """槽位顺序影响技能目标；不把只换显示 ID 的同一编成算作新选择。"""
    return json.dumps({
        key: option[key] for key in ("kind", "enemies", "power", "reward")
    }, sort_keys=True, ensure_ascii=False)


def choice_statistics(decisions: list[dict]) -> dict:
    """重复率只在非首领的多候选决策中计算，单路线单独报告。"""
    routes = [row for row in decisions if row["type"] == "node"]
    non_boss = [row for row in routes if not all(option["kind"] == "boss" for option in row["options"])]
    multiple = [row for row in non_boss if len(row["options"]) >= 2]
    duplicates = sum(
        len({option_key(option) for option in row["options"]}) < len(row["options"])
        for row in multiple
    )
    return {
        "route_decisions": len(routes), "non_boss_decisions": len(non_boss),
        "single_non_boss": sum(len(row["options"]) == 1 for row in non_boss),
        "multiple_non_boss": len(multiple), "duplicate_decisions": duplicates,
        "duplicate_rate_among_multiple": round(duplicates / len(multiple), 4) if multiple else None,
        "boss_decisions": len(routes) - len(non_boss),
    }


def initial_state(lineup: str, tier: str, seed: int, version: int) -> GameState:
    """使用真实弟子、技能和羁绊，从第一个 RNG 消费起选择路线版本。"""
    level, realm = TIERS[tier]
    state = GameState(
        resources=Resources(stamina=3),
        disciples=[
            DiscipleState(id=f"fixture_{index}", template_id=member, level=level, realm=realm)
            for index, member in enumerate(LINEUPS[lineup])
        ],
    )
    error = start_run(
        state, [member.id for member in state.disciples], load_disciples(), load_modes()["tower"],
        NOW, seed=seed, bonds=load_bonds(), skills=load_skills(), enemies=load_enemies(),
        affix_pool=load_affixes(), weapons=load_weapons(), route_version=version,
    )
    if error:
        raise RuntimeError(error)
    return state


def measure_campaign(
    lineup: str, tier: str, seed: int, version: int, policy: str,
    captured_states: list[dict] | None = None,
) -> dict:
    """保存真实决策、战果和结算奖励；分支取舍快照来自自然推进，不人工压血。"""
    state = initial_state(lineup, tier, seed, version)
    case_id = f"v{version}:{lineup}:{tier}:{seed}:{policy}"
    decisions, battles = [], []
    commands = {"start": 1, "choose": 0, "affix": 0, "settle": 0}
    run = state.active_run
    initial = run.model_dump(mode="json")
    for _ in range(run.party_snapshot.mode["node_count"] * 2 + 2):
        status = run_status(run)
        if status in {"cleared", "defeated"}:
            break
        if status == "choosing_affix":
            chosen = run.affix_options[0]
            decisions.append({"type": "affix", "after_floor": len(run.nodes), "options": list(run.affix_options), "chosen": chosen})
            error = pick_affix(state, chosen)
            commands["affix"] += 1
        else:
            options = visible_options(state)
            floor = len(run.nodes) + 1
            if captured_states is not None and version == 2 and floor in FORK_FLOORS and len(options) == 2:
                captured_states.append({"case_id": case_id, "floor": floor, "state": state.model_copy(deep=True)})
            index = select_route(options, policy)
            before = dict(run.member_hp)
            decision = {
                "type": "node", "floor": floor, "options": options, "chosen_index": index,
                "member_hp_before": before, "rng_cursor_before": run.rng_cursor,
            }
            error = choose(state, index)
            commands["choose"] += 1
            if error is None:
                battle = run.last_battle
                if battle is None:
                    raise RuntimeError("选路后缺少服务端战报")
                decision.update({
                    "member_hp_after": dict(run.member_hp), "rng_cursor_after": run.rng_cursor,
                    "won": battle.won, "loot": dict(battle.loot),
                })
                decisions.append(decision)
                battles.append({
                    **battle_metrics(battle, floor), "loot": dict(battle.loot),
                    "actual_enemies": [unit.template_id for unit in battle.initial_units if unit.side == "enemy"],
                    "actual_power": battle.enemy_power,
                })
        if error:
            raise RuntimeError(f"{case_id}: {status}: {error}")
    else:
        raise RuntimeError(f"{case_id}: 超过预期决策数")
    termination = run.end_reason or run_status(run)
    final_hp, pending = dict(run.member_hp), dict(run.pending_loot)
    cursor = run.rng_cursor
    result = settle_run(state, run.party_snapshot.mode, NOW)
    commands["settle"] += 1
    return {
        "id": case_id, "lineup": lineup, "party": list(LINEUPS[lineup]), "tier": tier,
        "seed": seed, "route_version": version, "policy": policy, "initial_run": initial,
        "termination": termination, "reached_floor": len(run.nodes), "member_hp_after": final_hp,
        "survivors": sum(hp > 0 for hp in final_hp.values()), "rng_cursor": cursor,
        "pending_loot": pending, "settled_loot": result["loot"], "commands": commands,
        "command_total": sum(commands.values()), "decisions": decisions, "battles": battles,
        "choice_statistics": choice_statistics(decisions),
    }


def fork_choices(captured: dict) -> dict:
    """克隆真实决策前存档逐条执行当前候选，不改原状态或未来策略。"""
    state = captured["state"]
    run = state.active_run
    options = visible_options(state)
    outcomes = []
    for index, option in enumerate(options):
        clone = state.model_copy(deep=True)
        error = choose(clone, index)
        if error:
            raise RuntimeError(error)
        fork = clone.active_run
        battle = fork.last_battle
        outcomes.append({
            "option": option, "won": battle.won, "reason": battle.reason,
            "member_hp_after": dict(fork.member_hp), "hp_after": fork.hp,
            "max_hp": fork.max_hp, "survivors": sum(hp > 0 for hp in fork.member_hp.values()),
            "loot": dict(battle.loot), "metrics": battle_metrics(battle, len(fork.nodes)),
        })
    return {
        "case_id": captured["case_id"], "floor": captured["floor"],
        "member_hp_before": dict(run.member_hp), "max_hp": run.max_hp,
        "affixes": list(run.affixes), "outcomes": outcomes,
    }


def find_tradeoffs(captured_states: list[dict], limit: int = 1) -> dict:
    """每对证据包含同候选下的两组真实状态；缺任一状态时不算偏好变化。"""
    groups = defaultdict(list)
    for captured in captured_states:
        options = visible_options(captured["state"])
        key = (captured["floor"], tuple(sorted(option_key(option) for option in options)))
        groups[key].append(captured)
    examples = []
    evaluated = 0
    for (floor, _), group in sorted(groups.items()):
        if len(group) < 2:
            continue
        reward_case = survival_case = None
        for captured in group:
            probe = fork_choices(captured)
            evaluated += 1
            options = [row["option"] for row in probe["outcomes"]]
            rich = select_route(options, "high_reward")
            safe = 1 - rich
            rich_result, safe_result = probe["outcomes"][rich], probe["outcomes"][safe]
            if options[rich]["reward"].get("cultivation", 0) <= options[safe]["reward"].get("cultivation", 0):
                continue
            alive_before = sum(hp > 0 for hp in probe["member_hp_before"].values())
            # 无新增阵亡且保留至少半血，才用“可承受高收益”描述这个具体分支。
            if (rich_result["won"] and safe_result["won"]
                    and rich_result["survivors"] == alive_before
                    and rich_result["hp_after"] >= probe["max_hp"] * .5):
                if reward_case is None:
                    reward_case = {**probe, "preferred_index": rich, "basis": "both_win_richer_route_keeps_team_and_half_hp", "input_state": captured["state"].model_dump(mode="json")}
            if safe_result["won"] and (not rich_result["won"] or safe_result["survivors"] > rich_result["survivors"]):
                if survival_case is None:
                    survival_case = {**probe, "preferred_index": safe, "basis": "lower_reward_avoids_failure_or_casualty", "input_state": captured["state"].model_dump(mode="json")}
            if reward_case and survival_case:
                examples.append({"floor": floor, "reward_state": reward_case, "survival_state": survival_case})
                break
        if len(examples) >= limit:
            break
    return {
        "captured_states": len(captured_states), "evaluated_states": evaluated,
        "candidate_groups": len(groups), "examples": examples,
        "missing_examples": max(0, limit - len(examples)),
        "scope": "each example pairs two actual states facing the same options; one next encounter per branch; no claim of globally optimal policy or play duration",
    }


def summarize(cases: list[dict]) -> list[dict]:
    """按版本与政策汇总，材料和货币逐项保留，不把修为当总收益。"""
    groups = defaultdict(list)
    for case in cases:
        groups[(case["route_version"], case["policy"])].append(case)
    result = []
    for (version, policy), rows in sorted(groups.items()):
        resources = sorted({key for row in rows for key in row["settled_loot"]})
        result.append({
            "route_version": version, "policy": policy, "cases": len(rows),
            "clears": sum(row["termination"] == "cleared" for row in rows),
            "avg_reached_floor": round(sum(row["reached_floor"] for row in rows) / len(rows), 4),
            "avg_commands": round(sum(row["command_total"] for row in rows) / len(rows), 4),
            "settled_loot_total": {key: round(sum(row["settled_loot"].get(key, 0) for row in rows), 2) for key in resources},
            "choice_statistics": choice_statistics([decision for row in rows for decision in row["decisions"]]),
        })
    return result


def run_suite() -> dict:
    captured_states, cases = [], []
    for version in (1, 2):
        for lineup in LINEUPS:
            for tier in TIERS:
                for seed in SEEDS:
                    for policy in POLICIES:
                        cases.append(measure_campaign(lineup, tier, seed, version, policy, captured_states))
    return {
        "format_version": 1, "suite": "t22_routes", "gameplay_input_sha256": gameplay_input_fingerprint(),
        "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "metrics_tool_sha256": hashlib.sha256((ROOT / "tools/measure_battles.py").read_bytes()).hexdigest(),
        "method": {
            "storage": "in-memory only; no database or real save access", "seeds": list(SEEDS),
            "tiers": TIERS, "lineups": LINEUPS, "policies": list(POLICIES),
            "affix_policy": "first visible option", "fork_floors": list(FORK_FLOORS),
            "route_versions": "1 uses retained legacy generator from the first draw; 2 uses current generator",
            "comparison_limit": "RNG consumption and encountered battles differ; not a single-variable causal experiment",
            "unavailable": ["actual UI click count", "thinking time", "network wait", "playback duration", "total human play duration"],
        },
        "cases": cases, "summary": summarize(cases), "tradeoffs": find_tradeoffs(captured_states),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/t22/current.json")
    args = parser.parse_args()
    report = run_suite()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"cases": len(report["cases"]), "tradeoffs": len(report["tradeoffs"]["examples"]), "missing_examples": report["tradeoffs"]["missing_examples"], "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
