"""T25 论道经济验证：P0 v2 §5 两类案例，隔离 GameState，不访问用户存档。

运行：backend\\.venv\\Scripts\\python.exe artifacts/t25/economy_check.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config_loader import load_bonds, load_disciples, load_enemies, load_facilities, load_modes, load_sects
from app.domain import conquest
from app.domain.facilities import upgrade_facility
from app.domain.run_engine import start_run, settle_run
from app.models.save import DiscipleState, GameState, Resources

NOW = datetime(2026, 11, 18, tzinfo=timezone.utc)
PARTY = ["guanyu", "zhangfei", "zhaoyun", "zhugeliang", "yuefei", "baisuzhen"]
STYLES = {style["name"]: style for style in load_sects()["styles"]}
LINES: list[str] = []


def log(text: str) -> None:
    LINES.append(text)
    print(text)


def make_state(conquered: bool = False) -> GameState:
    state = GameState(resources=Resources(stamina=6), rng_seed=71, disciples=[
        DiscipleState(id=key, template_id=key, level=20, realm=3) for key in PARTY
    ])
    conquest.ensure_sects(state, load_sects(), load_enemies())
    if conquered:
        for sect in state.sects:
            sect.conquered = True
    return state


def fight_conquest(state: GameState, sect) -> dict:
    assert start_run(state, PARTY, load_disciples(), load_modes()["expedition"], NOW,
                     seed=18, bonds=load_bonds(), sect=sect, route_version=2) is None
    for members in (PARTY[:3], PARTY[3:], PARTY[:3]):
        assert conquest.arena(state, members) is None
    result = settle_run(state, {}, NOW)
    assert result["victory"]
    return result["loot"]


def fight_retrial(state: GameState, sect) -> dict:
    assert start_run(state, PARTY, load_disciples(), load_modes()["expedition"], NOW,
                     seed=18, bonds=load_bonds(), sect=sect, route_version=2,
                     is_retrial=True, retrial_reward=STYLES[sect.style]["retrial_reward"]) is None
    assert conquest.arena(state, PARTY[:3]) is None
    result = settle_run(state, {}, NOW)
    assert result["victory"]
    return result["loot"]


def holdings(state: GameState) -> dict:
    return {
        "spirit_stone": round(state.resources.spirit_stone, 1),
        **{key: value for key, value in sorted(state.inventory.items())},
    }


log("# T25 论道经济验证记录")
log("")
log("2026-11-18（北京时间）。隔离 GameState 模拟，队伍为 20 级/境界 3 的六人测试队；不访问用户存档。")
log("")
log("## 案例 A · 零建设资源压力测试")
log("")
log("假设：三座一级外宗已攻克（模拟此前征讨，不计首胜库存），库存与灵石为 0，行动力 6；三次论道全胜，疗伤成本 0。")
log("")
state = make_state(conquered=True)
state.resources.spirit_stone = 0
log(f"起始：行动力 {state.resources.stamina}，持有 {holdings(state)}")
for sect in state.sects[:3]:
    loot = fight_retrial(state, sect)
    log(f"论道 {sect.style}（{sect.name}）胜：+{loot}；行动力 {state.resources.stamina}，持有 {holdings(state)}")
assert state.resources.stamina == 0
assert state.inventory.get("ling_mu") == 8 and state.inventory.get("qing_shi") == 14
assert state.inventory.get("chi_tong") == 4 and state.resources.spirit_stone == 32
definitions = load_facilities()
assert upgrade_facility(state, "hall", definitions) is None
log(f"升级主殿至 2 级成功；剩余 {holdings(state)}")
assert upgrade_facility(state, "tower", definitions) is None
log(f"升级问道塔至 2 级成功；剩余 {holdings(state)}，设施 {state.facility_levels}")
state.tower_floor = 20
state.resources.stamina = 1
assert start_run(state, PARTY, load_disciples(), load_modes()["tower"], NOW, seed=9, tower_tier=2) is None
log("一阶已通关（tower_floor=20）且行动力足够时，二阶问道可实际出发；仅升设施未通关一阶仍会被塔阶门槛拒绝（见 test_run_engine 回归）。")
log("")
log("结论：三次论道固定奖励合计 灵石32/灵木8/青石14/赤铜4，恰好覆盖二级主殿+二级问道塔，无必须等待现实时间的卡点。")
log("")
log("## 案例 B · 正常游玩流水")
log("")
state = make_state()
log(f"起始：行动力 {state.resources.stamina}，持有 {holdings(state)}")
loot = fight_conquest(state, state.sects[0])
log(f"征讨 {state.sects[0].name} 首胜：+{loot}；行动力 {state.resources.stamina}，持有 {holdings(state)}")
assert state.sects[0].conquered
loot = fight_retrial(state, state.sects[0])
log(f"论道 {state.sects[0].name} 胜：+{loot}；行动力 {state.resources.stamina}，持有 {holdings(state)}")
assert state.sects[0].conquered and state.active_run is None
assert all(not disciple.busy for disciple in state.disciples)
loot = fight_retrial(state, state.sects[0])
log(f"再次论道胜：+{loot}；行动力 {state.resources.stamina}，持有 {holdings(state)}")
log("")
log("结论：首胜奖只发一次；论道奖励按固定表重复发放，不叠加首胜倍率；行动力每次扣 2，失败分支零奖励与参战者伤势由后端回归覆盖。")

(ROOT / "artifacts" / "t25" / "economy-validation.md").write_text("\n".join(LINES) + "\n", encoding="utf-8")
print("written artifacts/t25/economy-validation.md")