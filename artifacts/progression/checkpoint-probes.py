"""补记主殿升级断点与同档三人论道对照；只使用隔离内存状态。

复现：backend/.venv/Scripts/python.exe artifacts/progression/checkpoint-probes.py
固定 map_30m / seed7，不调整配置、不补资源、不接触数据库或用户存档。
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import simulate_world_progression as simulation  # noqa: E402
from app.domain import items  # noqa: E402

SEED, SCENARIO, DAYS = 7, "map_30m", 7
TARGET, BATTLE_SEED = "sect_6", 321222
PARTIES = (
    {"name": "减攻治疗与单体输出", "members": ["baisuzhen", "huatuo", "houyi"],
     "reason": "白素贞减攻承伤，华佗治疗，后羿提供单体输出。"},
    {"name": "减攻破甲与护盾", "members": ["baisuzhen", "jingwei", "zhugeliang"],
     "reason": "白素贞减攻承伤，精卫破甲，诸葛亮以护盾代替持续治疗。"},
)
OUTPUT = ROOT / "artifacts/progression/formal-checkpoint-probes.json"


def state_hash(state):
    return hashlib.sha256(state.model_dump_json().encode()).hexdigest()


def inputs(state):
    """保存影响本次比较的真实培养、物品、岗位与地区输入。"""
    return {
        "state_sha256": state_hash(state), "resources": state.resources.model_dump(),
        "inventory": dict(state.inventory), "facility_levels": dict(state.facility_levels),
        "disciples": [disciple.model_dump(mode="json") for disciple in state.disciples],
        "gear": {key: value.model_dump(mode="json") for key, value in state.gear.items()},
        "weapon_levels": dict(state.weapon_levels), "global_bonuses": dict(state.bonuses),
        "duty_slots": [slot.model_dump(mode="json") for slot in state.duty_slots],
        "garrisons": {sect.id: [slot.model_dump(mode="json") for slot in sect.garrison]
                      for sect in state.sects if sect.garrison},
        "world": state.world.model_dump(mode="json"),
    }


def launch_check(sim, state, node, now, practice=False, zero_stamina=False):
    """克隆状态后调用真实出发校验；零行动力分支只减少行动力。"""
    trial = deepcopy(state)
    if zero_stamina:
        trial.resources.stamina = 0
    party = [disciple.id for disciple in trial.disciples[:6] if not disciple.busy]
    sect, reward = None, None
    mode = simulation.world.tower_mode(trial, sim.modes["tower"], sim.world)
    if node.kind == "sect":
        sect = next((value for value in trial.sects if value.id == node.sect_id), None)
        if node.locked or sect is None:
            return {"id": node.id, "reason": node.reason or "宗门未生成", "can_start": False}
        mode = deepcopy(sim.modes["expedition"])
        if sect.conquered:
            style = next(value for value in simulation.load_sects()["styles"] if value["name"] == sect.style)
            scale = next(value["reward_scale"] for value in sim.world["regions"] if value["id"] == sect.region_id)
            reward = {key: value * scale for key, value in style["retrial_reward"].items()}
    else:
        prepared, error = simulation.world.prepare_world_node(trial, node.id, sim.world, practice=practice)
        if error:
            return {"id": node.id, "reason": error, "can_start": False}
        mode.update(prepared["mode_overrides"])
        mode.update(id="tower" if node.kind == "tower" else "dungeon" if node.kind == "dungeon" else "world",
                    world_node=prepared, gear_tier=node.gear_tier, gear_slot=node.gear_slot,
                    opportunities=node.kind == "dungeon")
    before = trial.resources.stamina
    error = simulation.run_engine.start_run(
        trial, party, sim.templates, mode, now, seed=BATTLE_SEED,
        bonds=sim.bonds, skills=sim.skills, enemies=sim.enemies, affix_pool=[],
        weapons=sim.weapons, route_version=2, sect=sect,
        is_retrial=reward is not None, retrial_reward=reward,
    )
    return {"id": node.id, "name": node.name, "kind": node.kind, "practice": practice,
            "counterfactual_zero_stamina": zero_stamina, "can_start": error is None,
            "reason": error or "", "stamina_before": before,
            "stamina_cost": before - trial.resources.stamina,
            "permanent_reward_available": not practice and (not node.cleared or node.kind in {"sect", "raid", "dungeon", "tower"})}


def hall_checkpoint(sim, before, after, now):
    """领域升级返回时立即取样；新宗门投影仅在副本执行正常补齐。"""
    protected = state_hash(after)
    old, current = deepcopy(before), deepcopy(after)
    for state in (old, current):
        simulation.conquest.ensure_sects(state, simulation.load_sects(), sim.enemies, sim.world)
    assert current.resources == after.resources and current.inventory == after.inventory
    old_nodes = next(region.nodes for region in simulation.world.world_view(old, sim.world).regions if region.selected)
    nodes = next(region.nodes for region in simulation.world.world_view(current, sim.world).regions if region.selected)
    previous_open = {node.id for node in old_nodes if not node.locked}
    checks = [launch_check(sim, current, node, now) for node in nodes]
    free = []
    for node in nodes:
        if node.kind not in {"gate", "invasion", "raid"}:
            continue
        if node.stamina_cost == 0:
            free.append(launch_check(sim, current, node, now, zero_stamina=True))
        free.append(launch_check(sim, current, node, now, practice=True, zero_stamina=True))
    assert any(check["can_start"] for check in free)
    assert state_hash(after) == protected
    return {
        "at": now.isoformat(), "hours": sim.elapsed(),
        "from_level": before.facility_levels["hall"], "to_level": after.facility_levels["hall"],
        "before_resources": before.resources.model_dump(), "before_inventory": dict(before.inventory),
        "after": inputs(current), "source_state_sha256_before_projection": protected,
        "projection_note": "升级返回即刻克隆；按正常流程ensure_sects补齐新宗门，无资源变化。",
        "newly_opened_nodes": [node.id for node in nodes if not node.locked and node.id not in previous_open],
        "map_nodes": [node.model_dump(mode="json") for node in nodes],
        "formal_launch_checks": checks, "zero_stamina_launch_checks": free,
        "note": "can_start仅证明真实入口校验可通过，不表示一定打得过；未结算这些出发副本。",
    }


def compare_parties(sim, source, now):
    protected = state_hash(source)
    common = deepcopy(source)
    initial = inputs(common)
    healing = []
    # 只服用真实库存，不补炼、不补发丹药；无库存的伤势如实保留。
    for disciple in sorted(common.disciples, key=lambda value: -value.injury_stacks):
        if disciple.injury_stacks <= 0:
            continue
        if items.pill_stock(common, "liao_shang_dan") < 1:
            healing.append({"id": disciple.id, "healed": False, "reason": "实际库存没有疗伤丹"})
            continue
        error = items.use_pill(common, disciple.id, "liao_shang_dan", sim.recipes, sim.templates)
        assert error is None, error
        healing.append({"id": disciple.id, "healed": True, "reason": "消耗实际库存一颗疗伤丹"})
    assert common.resources == source.resources
    common_hash = state_hash(common)
    owned = {disciple.id for disciple in common.disciples}
    results = []
    for choice in PARTIES:
        assert set(choice["members"]) <= owned
        trial = deepcopy(common)
        sect = next(value for value in trial.sects if value.id == TARGET)
        assert sect.conquered and sect.region_id == 1 and sect.area == 2
        style = next(value for value in simulation.load_sects()["styles"] if value["name"] == sect.style)
        scale = next(value["reward_scale"] for value in sim.world["regions"] if value["id"] == sect.region_id)
        reward = {key: value * scale for key, value in style["retrial_reward"].items()}
        mode = deepcopy(sim.modes["expedition"])
        error = simulation.run_engine.start_run(
            trial, choice["members"], sim.templates, mode, now, seed=BATTLE_SEED,
            bonds=sim.bonds, skills=sim.skills, enemies=sim.enemies, affix_pool=[],
            weapons=sim.weapons, route_version=2, sect=sect, is_retrial=True, retrial_reward=reward,
        )
        assert error is None, error
        run = trial.active_run
        frozen_input = {
            "seed": run.run_seed, "party": list(run.party), "retrial_reward": dict(run.retrial_reward),
            "combatants": [unit.model_dump(mode="json") for unit in run.party_snapshot.combatants],
            "bonds": [bond.model_dump(mode="json") for bond in run.party_snapshot.bonds],
            "target": {"id": sect.id, "name": sect.name, "region_id": sect.region_id,
                       "area": sect.area, "style": sect.style, "conquered": sect.conquered,
                       "leader": sect.leader.model_dump(mode="json")},
            "resources_after_start": trial.resources.model_dump(),
            "member_hp_before": dict(run.member_hp),
        }
        assert source.resources.stamina - trial.resources.stamina == mode["stamina_cost"]
        error = simulation.conquest.arena(trial, choice["members"])
        assert error is None, error
        battle = trial.active_run.last_battle.model_dump(mode="json")
        settled = simulation.run_engine.settle_run(trial, {}, now)
        results.append({
            **choice, "input": frozen_input, "battle": battle,
            "settlement": {"victory": settled["victory"], "loot": settled["loot"],
                           "gear": [item.model_dump(mode="json") for item in settled["gear"]]},
            "resources_after": trial.resources.model_dump(), "inventory_after": dict(trial.inventory),
            "disciples_after": [disciple.model_dump(mode="json") for disciple in trial.disciples],
        })
        assert state_hash(common) == common_hash and state_hash(source) == protected
    return {"source_before_healing": initial, "healing": healing,
            "shared_input_after_healing": inputs(common), "results": results,
            "source_unchanged": state_hash(source) == protected,
            "note": "同一真实培养存档选择不同三人，各人原等级/境界/装备/余留伤势均保留；不是等等级职业强度比较，也不是不同招募路线的端到端平衡。"}


def main():
    sim = simulation.Simulation(SEED, SCENARIO, "formal")
    hall_records, first_clear_now = [], None
    original_upgrade, original_play = simulation.upgrade_facility, sim.play_run

    def observed_upgrade(state, identity, definitions):
        before = deepcopy(state) if state is sim.state and identity == "hall" else None
        error = original_upgrade(state, identity, definitions)
        if error is None and before is not None:
            hall_records.append(hall_checkpoint(sim, before, state, sim.now))
        return error

    def observed_play(*args, **kwargs):
        nonlocal first_clear_now
        value = original_play(*args, **kwargs)
        if first_clear_now is None and sim.first_clear_state is not None:
            first_clear_now = sim.now
        return value

    simulation.upgrade_facility, sim.play_run = observed_upgrade, observed_play
    try:
        result = sim.simulate(DAYS)
    finally:
        simulation.upgrade_facility = original_upgrade
    old_report = json.loads((ROOT / "artifacts/progression/formal-growth-policy-v4-summary.json").read_text(encoding="utf-8"))
    expected = next(row for row in old_report["results"] if row["seed"] == SEED and row["scenario"] == SCENARIO)
    assert result["first_token"] == expected["first_token"], "探针观测不得改变既有真实轨迹"
    assert sim.first_clear_state is not None and first_clear_now is not None
    assert [item["to_level"] for item in hall_records] == [2, 3]
    compared = compare_parties(sim, sim.first_clear_state, first_clear_now)
    checksum = hashlib.sha256()
    files = [path for path in (ROOT / "config").rglob("*.json") if not any(part in {"assets", "ui", "style"} for part in path.parts)]
    for path in sorted(files):
        checksum.update(path.relative_to(ROOT).as_posix().encode())
        checksum.update(path.read_bytes())
    assert checksum.hexdigest() == old_report["config_sha256"]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reproduce_command": "backend/.venv/Scripts/python.exe artifacts/progression/checkpoint-probes.py",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "simulation_tool_sha256": hashlib.sha256((ROOT / "tools/simulate_world_progression.py").read_bytes()).hexdigest(),
        "config_sha256": checksum.hexdigest(), "policy_version": old_report["policy_version"],
        "fixed_inputs": {"seed": SEED, "scenario": SCENARIO, "days": DAYS,
                         "battle_seed": BATTLE_SEED, "target_sect": TARGET, "parties": PARTIES},
        "source_first_token": result["first_token"], "first_clear_at": first_clear_now.isoformat(),
        "reproduces_existing_first_token": True, "hall_upgrades": hall_records,
        "party_comparison": compared,
        "limits": ["所有探针只操作隔离内存和深拷贝，不读取数据库或真实用户存档。",
                   "不筛选种子、目标或战果，不改变玩法配置；失败如实保留。",
                   "主殿节点可出发不代表可通关；零行动力检查在副本降低行动力，未添加其他资源。",
                   "疗伤只用已有药品，不补炼；不同角色保留原培养差异，未验证其他招募路径。",
                   "不属于人工游玩、视觉验收、全阵容或第二地区长期平衡验证。"],
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "source_sha256": payload["source_sha256"],
                      "report_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
                      "hall_levels": [item["to_level"] for item in hall_records],
                      "first_token_day": result["first_token"]["day"],
                      "parties": [{"name": value["name"], "victory": value["settlement"]["victory"],
                                   "rounds": value["battle"]["rounds"]} for value in compared["results"]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
