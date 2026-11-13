"""T21 同候选对照：从同一决策前状态分别选不同道法，比较后续实际结果。

其余输入完全一致：同一 run_seed、同一后续策略（每层取首个候选、词条取首个）。
输出为 JSON，供 balance-report 引用。
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config_loader import load_disciples, load_modes  # noqa: E402
from app.domain.run_engine import choose, pick_affix, run_status, start_run  # noqa: E402
from app.models.save import DiscipleState, GameState, Resources  # noqa: E402

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
DEFAULT_PARTY = ["guanyu", "zhangfei", "zhaoyun", "zhugeliang", "yuefei", "houyi"]


def make_state(level: int, realm: int, party: list[str]) -> GameState:
    """构造固定培养档位的队伍。"""
    return GameState(
        resources=Resources(stamina=99),
        disciples=[
            DiscipleState(id=key, template_id=key, level=level, realm=realm)
            for key in party
        ],
    )


def advance(state: GameState, target_step: int, owned: list[str]) -> None:
    """推进到目标层之前；owned 中的道法直接注入，沿途选择取首个候选。"""
    run = state.active_run
    run.affixes = list(owned)
    while run_status(run) in {"choosing_node", "choosing_affix"} and len(run.nodes) < target_step:
        if run.affix_pending:
            pick_affix(state, run.affix_options[0])
        else:
            choose(state, 0)


def finish(state: GameState) -> dict:
    """跑完剩余部分，按战报区分对敌输出与对我方承伤。"""
    run = state.active_run
    dealt = taken = healed = absorbed = rounds = 0
    while run_status(run) in {"choosing_node", "choosing_affix"}:
        if run.affix_pending:
            pick_affix(state, run.affix_options[0])
            continue
        choose(state, 0)
        battle = run.last_battle
        if not battle:
            continue
        rounds += battle.rounds
        for event in battle.events:
            for effect in event.effects:
                if effect.kind == "heal":
                    healed += effect.amount
                elif effect.kind == "damage":
                    if effect.target_id.startswith("enemy:"):
                        dealt += effect.amount
                    else:
                        taken += effect.amount
                absorbed += effect.absorbed
    return {
        "layers": len(run.nodes),
        "dealt": dealt,
        "taken": taken,
        "healed": healed,
        "absorbed": absorbed,
        "rounds": rounds,
        "alive": sum(1 for hp in run.member_hp.values() if hp > 0),
        "hp": run.hp,
    }


def compare(seed: int, step: int, level: int, realm: int, hp_ratio: float, owned: list[str], party: list[str]) -> dict:
    """在同一决策点克隆状态，分别选择每个候选并跑完。"""
    state = make_state(level, realm, party)
    start_run(state, party, load_disciples(), load_modes()["tower"], NOW, seed=seed)
    advance(state, step, owned)

    run = state.active_run
    if hp_ratio < 1:
        run.member_hp = {
            unit_id: max(1, int(hp * hp_ratio)) for unit_id, hp in run.member_hp.items()
        }
        run.hp = sum(run.member_hp.values())

    options = list(run.affix_options)
    results = {}
    for option in options:
        clone = state.model_copy(deep=True)
        pick_affix(clone, option)
        results[option] = finish(clone)

    return {
        "seed": seed,
        "step": step,
        "level": level,
        "realm": realm,
        "hp_ratio": hp_ratio,
        "owned": owned,
        "party": party,
        "options": options,
        "results": results,
    }


def main() -> int:
    """命令行入口：输出一组对照 JSON。"""
    parser = argparse.ArgumentParser(description="T21 同候选对照")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--step", type=int, default=6)
    parser.add_argument("--level", type=int, default=4)
    parser.add_argument("--realm", type=int, default=2)
    parser.add_argument("--hp-ratio", type=float, default=1.0)
    parser.add_argument("--owned", default="", help="逗号分隔的已拥有道法 id")
    parser.add_argument("--party", default=",".join(DEFAULT_PARTY))
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    owned = [item for item in args.owned.split(",") if item]
    report = compare(
        args.seed, args.step, args.level, args.realm, args.hp_ratio, owned,
        [item for item in args.party.split(",") if item],
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
