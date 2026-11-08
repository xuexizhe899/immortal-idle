"""出征引擎：节点生成、自动战斗、结算。

随机只决定"出现哪些候选"，战斗与收益公式完全确定性，便于重放与测试。
所有数值来自模式配置（`config/modes/*.json`），换模式不需要改代码。
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime

from app.domain.affix import draw
from app.domain.injuries import apply_injury, attack_multiplier
from app.domain.rng import Pcg32
from app.models.save import ActiveRun, DiscipleState, GameState, RunNode

MAX_PARTY = 5


@dataclass
class BattleResult:
    """一次战斗的结果。"""

    won: bool
    damage: int
    enemy_power: int
    party_power: float


def bond_bonus(party_ids: list[str], bonds: dict[str, dict]) -> dict[str, float]:
    """计算队伍触发的羁绊加成（加区百分比），只统计 run 作用域。"""
    active = set(party_ids)
    bonus: dict[str, float] = {}

    for bond in bonds.values():
        members = set(bond["members"])
        if len(members & active) < bond.get("requires", len(members)):
            continue
        for effect in bond.get("effects", []):
            if effect["scope"] != "run" or effect["mode"] != "add_pct":
                continue
            bonus[effect["stat"]] = bonus.get(effect["stat"], 0.0) + effect["value"]

    return bonus


def party_power(
    party: list[DiscipleState],
    templates: dict[str, dict],
    bonus: dict[str, float] | None = None,
) -> float:
    """队伍战力：攻击为主，防御与气血加权，等级线性放大，可叠加羁绊加成。"""
    bonus = bonus or {}
    atk_mult = 1 + bonus.get("atk", 0.0)
    def_mult = 1 + bonus.get("def", 0.0)
    hp_mult = 1 + bonus.get("hp", 0.0)

    total = 0.0
    for disciple in party:
        template = templates.get(disciple.template_id)
        if template is None:
            continue
        base = template["base_stats"]
        attack = base["atk"] * attack_multiplier(disciple.injury_stacks) * atk_mult
        total += (
            attack + base["def"] * 0.5 * def_mult + base["hp"] * 0.1 * hp_mult
        ) * (1 + 0.1 * (disciple.level - 1))
    return total


def enemy_power(step: int, mode: dict) -> int:
    """第 step 层敌人的战力，随层数线性增长。"""
    return mode["base_enemy_power"] * (step + 1)


def node_reward(kind: str, mode: dict) -> dict[str, float]:
    """节点战利品，从模式配置取；未知类型退回普通战斗奖励。"""
    return dict(mode["rewards"].get(kind, mode["rewards"]["battle"]))


def roll_choices(rng: Pcg32, step: int, mode: dict) -> list[RunNode]:
    """生成某一层的候选节点；同种子必得同一组。"""
    last_step = step >= mode["node_count"] - 1
    count = 1 if last_step else mode["choices_per_step"]
    nodes: list[RunNode] = []

    for _ in range(count):
        if last_step:
            kind = "boss"
        else:
            kind = "elite" if rng.randint(1, 100) <= mode["elite_chance"] else "battle"
        nodes.append(
            RunNode(
                kind=kind,
                enemy=f"{kind}_{step}",
                power=enemy_power(step, mode),
                reward=node_reward(kind, mode),
            )
        )
    return nodes


def fight(strength: float, enemy: int, hp: int) -> BattleResult:
    """确定性战斗：战力低于敌人直接失败，否则按战力比扣血。"""
    if strength < enemy:
        return BattleResult(won=False, damage=hp, enemy_power=enemy, party_power=strength)

    damage = max(1, round(enemy * 100 / strength))
    return BattleResult(
        won=hp - damage > 0,
        damage=damage,
        enemy_power=enemy,
        party_power=strength,
    )


def run_status(run: ActiveRun, mode: dict) -> str:
    """推导当前状态：defeated / cleared / choosing_affix / choosing_node。"""
    if run.hp <= 0:
        return "defeated"
    if len(run.nodes) >= mode["node_count"]:
        return "cleared"
    if run.affix_pending:
        return "choosing_affix"
    return "choosing_node"


def start_run(
    state: GameState,
    party_ids: list[str],
    templates: dict[str, dict],
    mode: dict,
    now: datetime,
    seed: int | None = None,
) -> str | None:
    """开始一次出征；成功返回 None，失败返回原因。"""
    if state.active_run is not None:
        return "已有进行中的出征"
    if not party_ids or len(party_ids) > MAX_PARTY:
        return f"队伍需要 1 到 {MAX_PARTY} 名弟子"
    if len(set(party_ids)) != len(party_ids):
        return "队伍中有重复弟子"
    if state.resources.stamina < mode["stamina_cost"]:
        return "行动力不足"

    by_id = {d.id: d for d in state.disciples}
    for disciple_id in party_ids:
        disciple = by_id.get(disciple_id)
        if disciple is None:
            return f"弟子 {disciple_id} 不存在"
        if disciple.busy:
            return f"弟子 {disciple_id} 正在出征"
        if disciple.template_id not in templates:
            return f"弟子 {disciple_id} 模板未配置"

    run_seed = seed if seed is not None else secrets.randbits(63)
    rng = Pcg32(run_seed)

    state.resources.stamina -= mode["stamina_cost"]
    for disciple_id in party_ids:
        by_id[disciple_id].busy = True

    state.active_run = ActiveRun(
        run_seed=run_seed,
        rng_cursor=0,
        mode=mode["id"],
        party=list(party_ids),
        hp=mode["start_hp"],
        max_hp=mode["start_hp"],
        choices=roll_choices(rng, 0, mode),
        started_at=now,
    )
    state.active_run.rng_cursor = rng.cursor
    return None


def choose(
    state: GameState,
    choice_index: int,
    templates: dict[str, dict],
    affix_pool: list[dict],
    mode: dict,
    bonds: dict[str, dict],
) -> str | None:
    """选择节点并自动战斗；成功返回 None，失败返回原因。"""
    run = state.active_run
    if run is None:
        return "没有进行中的出征"
    if run.hp <= 0:
        return "出征已结束，请结算"
    if len(run.nodes) >= mode["node_count"]:
        return "已通关，请结算"
    if run.affix_pending:
        return "请先选择词条"
    if not 0 <= choice_index < len(run.choices):
        return "无效的节点选择"

    node = run.choices[choice_index]
    run.nodes.append(node)
    run.choices = []

    party = [d for d in state.disciples if d.id in run.party]
    strength = party_power(party, templates, bond_bonus(run.party, bonds))
    result = fight(strength, node.power, run.hp)
    run.hp = max(0, run.hp - result.damage)

    if not result.won:
        return None

    for key, value in node_reward(node.kind, mode).items():
        run.pending_loot[key] = run.pending_loot.get(key, 0.0) + value

    if len(run.nodes) >= mode["node_count"]:
        return None

    rng = Pcg32(run.run_seed)
    rng.advance_to(run.rng_cursor)

    if affix_pool:
        run.affix_options = draw(rng, affix_pool, group_counts(run.affixes, affix_pool))
        run.affix_pending = True
    else:
        run.choices = roll_choices(rng, len(run.nodes), mode)

    run.rng_cursor = rng.cursor
    return None


def group_counts(affix_ids: list[str], pool: list[dict]) -> dict[str, int]:
    """统计已选词条分别属于哪些协同组、各几个。"""
    by_id = {affix["id"]: affix for affix in pool}
    counts: dict[str, int] = {}
    for affix_id in affix_ids:
        group = by_id.get(affix_id, {}).get("group")
        if group:
            counts[group] = counts.get(group, 0) + 1
    return counts


def pick_affix(state: GameState, affix_id: str, mode: dict) -> str | None:
    """选中一个词条并推进到下一层；成功返回 None，失败返回原因。"""
    run = state.active_run
    if run is None:
        return "没有进行中的出征"
    if not run.affix_pending:
        return "当前没有待选词条"
    if affix_id not in run.affix_options:
        return "该词条不在候选中"

    run.affixes.append(affix_id)
    run.affix_options = []
    run.affix_pending = False

    rng = Pcg32(run.run_seed)
    rng.advance_to(run.rng_cursor)
    run.choices = roll_choices(rng, len(run.nodes), mode)
    run.rng_cursor = rng.cursor
    return None


def defeat_loot(pending: dict[str, float], cleared: int, mode: dict) -> dict[str, float]:
    """失败收益：已累积战利品按比例折算，再按到达层数给保底，避免断粮。"""
    loot = {
        key: round(value * mode["defeat_ratio"], 2) for key, value in pending.items()
    }
    for key, value in mode["defeat_floor_reward"].items():
        loot[key] = round(loot.get(key, 0.0) + value * cleared, 2)
    return loot


def settle_run(state: GameState, mode: dict, now: datetime) -> dict:
    """结算出征：发收益、失败挂伤、清空 run 并解除占用。"""
    run = state.active_run
    cleared = len(run.nodes)
    victory = run.hp > 0 and cleared >= mode["node_count"]
    loot = (
        {key: round(value, 2) for key, value in run.pending_loot.items()}
        if victory
        else defeat_loot(run.pending_loot, cleared, mode)
    )

    state.resources.cultivation += loot.get("cultivation", 0.0)
    state.resources.spirit_stone += loot.get("spirit_stone", 0.0)
    state.tower_floor = max(state.tower_floor, cleared)

    by_id = {d.id: d for d in state.disciples}
    for disciple_id in run.party:
        disciple = by_id.get(disciple_id)
        if disciple is None:
            continue
        disciple.busy = False
        if not victory:
            apply_injury(disciple, now)

    state.active_run = None
    return {"cleared": cleared, "victory": victory, "loot": loot}
