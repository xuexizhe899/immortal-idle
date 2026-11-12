#!/usr/bin/env python3
"""在内存中复现六人阵容对照及人工 6v6 满回合压力场景。

运行：backend/.venv/Scripts/python.exe tools/measure_battles.py
仅读取配置与代码，不连接数据库，不读取本地 .env，不改变真实存档。
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
    load_affixes, load_bonds, load_disciples, load_enemies, load_modes, load_skills,
)
from app.domain.battle import ROUND_LIMIT, simulate_battle  # noqa: E402
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


def input_fingerprint() -> str:
    """哈希仅覆盖战斗输入与执行代码，不包含环境文件或机器标识。"""
    paths = [ROOT / "config" / "modes" / "tower.json"]
    for folder in ("disciples", "skills", "bonds", "affixes", "enemies"):
        paths.extend(sorted((ROOT / "config" / folder).glob("*.json")))
    paths.extend(ROOT / path for path in (
        "backend/app/domain/battle.py", "backend/app/domain/run_engine.py",
        "backend/app/domain/progression.py", "backend/app/models/battle.py",
        "backend/app/models/save.py", "tools/measure_battles.py",
    ))
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def state_bytes(state: GameState) -> int:
    return len(state.model_dump_json().encode("utf-8"))


def measure_campaign(lineup: str, party: tuple[str, ...], level: int, seed: int) -> dict:
    """相同等级、种子与首项选择策略下跑完出征，记录真实结果而非估算胜率。"""
    templates, skills, bonds = load_disciples(), load_skills(), load_bonds()
    enemies, mode, affixes = load_enemies(), load_modes()["tower"], load_affixes()
    state = GameState(
        resources=Resources(stamina=3),
        disciples=[DiscipleState(id=f"fixture_{index}", template_id=template_id, level=level, realm=1) for index, template_id in enumerate(party)],
        unlocks=list(party),
    )
    began = perf_counter()
    error = start_run(
        state, [disciple.id for disciple in state.disciples], templates, mode, NOW,
        seed=seed, bonds=bonds, skills=skills, enemies=enemies, affix_pool=affixes,
    )
    if error:
        raise RuntimeError(f"{lineup}: start_run: {error}")
    peak_bytes = state_bytes(state)
    battles: list[dict] = []
    triggered: Counter[str] = Counter()
    for _ in range(mode["node_count"] * 2 + 2):
        run = state.active_run
        if run is None:
            raise RuntimeError("出征意外消失")
        status = run_status(run)
        if status in {"cleared", "defeated"}:
            break
        if status == "choosing_affix":
            error = pick_affix(state, run.affix_options[0])
        else:
            error = choose(state, 0)
            if error is None:
                battle = run.last_battle
                if battle is None:
                    raise RuntimeError("战斗结束却没有服务端战报")
                for event in battle.events:
                    triggered.update(event.bonds)
                battles.append({
                    "floor": len(run.nodes), "kind": battle.node.kind,
                    "won": battle.won, "reason": battle.reason,
                    "remaining_hp": run.hp, "rounds": battle.rounds,
                    "main_actions": len(battle.events),
                    "effect_results": sum(len(event.effects) for event in battle.events),
                    "triggered_bonds": sorted({bond for event in battle.events for bond in event.bonds}),
                })
        if error:
            raise RuntimeError(f"{lineup}: {status}: {error}")
        peak_bytes = max(peak_bytes, state_bytes(state))
    else:
        raise RuntimeError("出征超过预期节点决策次数")
    run = state.active_run
    remaining_hp, reached_floor = run.hp, len(run.nodes)
    result = settle_run(state, mode, NOW)
    elapsed_ms = (perf_counter() - began) * 1000
    return {
        "lineup": lineup, "party": list(party),
        "rarities": [templates[member]["rarity"] for member in party],
        "level": level, "realm": 1, "seed": seed,
        "reached_floor": reached_floor,
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "t16" / "benchmark.json")
    parser.add_argument("--repetitions", type=int, default=5, help="人工满回合场景测量次数，默认5")
    args = parser.parse_args()
    if MAX_PARTY != 6 or not 1 <= args.repetitions <= 20:
        parser.error("需要已接入的六人战斗引擎，repetitions 必须是1..20")
    fingerprint = input_fingerprint()
    campaigns = [measure_campaign(name, party, level, seed) for name, party in LINEUPS.items() for level in LEVELS for seed in SEEDS]
    fixture = measure_full_round_fixture(args.repetitions)
    if fingerprint != input_fingerprint():
        raise RuntimeError("测量期间输入文件改变，请在修改稳定后重新运行")
    report = {
        "format_version": 1, "input_sha256": fingerprint,
        "command": "backend/.venv/Scripts/python.exe tools/measure_battles.py",
        "environment": {"python": platform.python_version(), "platform": platform.system(), "architecture": platform.machine()},
        "method": {
            "storage": "in-memory GameState only; no database access",
            "seeds": list(SEEDS), "levels": list(LEVELS), "realm": 1,
            "policy": "Always choose route index 0 and affix option index 0.",
            "notes": "36 deterministic campaign observations, not a probability estimate. Timing includes simulation and state serialization; no front-end playback or network.",
            "substitution": "mechanics_core: replace rarity-3 Yue Fei/Zhao Yun with rarity-1 Du Fu/Jing Wei; keep the other four members and their order.",
        },
        "campaigns": campaigns, "full_round_fixture": fixture,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "campaigns": len(campaigns), "input_sha256": fingerprint,
        "fixture_main_actions": fixture["main_actions"],
        "fixture_median_wall_ms": fixture["median_wall_ms"],
        "max_campaign_state_json_bytes": max(case["peak_state_json_bytes"] for case in campaigns),
        "output": str(args.output),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
