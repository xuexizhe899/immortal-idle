#!/usr/bin/env python3
"""固定十二组初期征讨案例，只在内存中调用正式生成与战斗规则。"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config_loader import (  # noqa: E402
    load_affixes, load_bonds, load_disciples, load_enemies, load_modes, load_sects, load_skills, load_weapons,
)
from app.domain.conquest import arena, ensure_sects  # noqa: E402
from app.domain.run_engine import run_status, start_run  # noqa: E402
from app.models.save import DiscipleState, GameState, Resources  # noqa: E402

NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)
WORLD_SEED = 71
RUN_SEED = 1
PARTIES = (
    ("dufu", "jingwei", "libai"),
    ("zhangfei", "libai", "huatuo"),
    ("baisuzhen", "huatuo", "houyi"),
    ("guanyu", "huatuo", "libai"),
)


def measure() -> dict:
    definitions = {
        "disciples": load_disciples(), "enemies": load_enemies(), "modes": load_modes(),
        "sects": load_sects(), "skills": load_skills(), "bonds": load_bonds(),
        "weapons": load_weapons(), "affixes": load_affixes(),
    }
    fingerprint = hashlib.sha256(json.dumps(definitions, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    cases = []
    for party in PARTIES:
        for target in range(3):
            state = GameState(resources=Resources(stamina=3), rng_seed=WORLD_SEED, disciples=[
                DiscipleState(id=key, template_id=key) for key in party
            ])
            ensure_sects(state, definitions["sects"], definitions["enemies"])
            sect = state.sects[target]
            error = start_run(
                state, list(party), definitions["disciples"], definitions["modes"]["expedition"], NOW,
                seed=RUN_SEED, bonds=definitions["bonds"], skills=definitions["skills"],
                enemies=definitions["enemies"], weapons=definitions["weapons"], affix_pool=[], sect=sect,
            )
            if error:
                raise RuntimeError(error)
            rounds = []
            while run_status(state.active_run) == "choosing_node":
                run = state.active_run
                guard_before = run.guard
                error = arena(state, list(party))
                if error:
                    raise RuntimeError(error)
                battle = run.last_battle
                rounds.append({
                    "stage": "leader" if battle.node.kind == "boss" else "arena",
                    "arena_round": run.arena_round, "guard_before": guard_before, "guard_after": run.guard,
                    "won": battle.won, "reason": battle.reason, "combat_rounds": battle.rounds,
                    "surviving_allies": [unit.id for unit in battle.final_units if unit.side == "ally" and unit.hp > 0],
                    "member_hp": dict(run.member_hp),
                })
            cases.append({
                "party": list(party),
                "recruitment_cost": sum(definitions["disciples"][key]["unlock_cost"]["reputation"] for key in party),
                "sect_id": sect.id, "sect_name": sect.name, "style": sect.style,
                "rounds": rounds, "end_reason": run.end_reason,
                "boss_result": next(("victory" if row["won"] else row["reason"] for row in rounds if row["stage"] == "leader"), "not_reached"),
                "victory": run_status(run) == "cleared",
            })
    return {
        "world_seed": WORLD_SEED, "run_seed": RUN_SEED, "config_sha256": fingerprint,
        "conditions": "一级宗门；所有弟子1级1境界、无伤势、无装备与永久增益；每场原三人按原顺序上阵；残血继承。",
        "limitations": "十二个确定性初期案例仅验证首级可攻克性与阵容差异，不代表全部阵容、后期数值或视觉验收。",
        "case_count": len(cases), "victories": sum(case["victory"] for case in cases), "cases": cases,
    }


if __name__ == "__main__":
    report = measure()
    destination = ROOT / "artifacts/sect-conquest/balance-baseline.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{report['case_count']} cases, {report['victories']} victories; {destination}")
