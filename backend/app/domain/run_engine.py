"""出征推进：固定定义、六人编队、自动战斗与一次性战利品结算。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from math import floor
import secrets

from app.config_loader import load_affixes, load_enemies, load_skills
from app.domain.affix import draw, pick_group
from app.domain.battle import simulate_battle
from app.domain.injuries import apply_injury, attack_multiplier
from app.domain.progression import LEVEL_GROWTH, REALM_GROWTH
from app.domain.rng import Pcg32
from app.models.battle import BattleBond, BattleUnit, EnemyDefinition, SkillDefinition
from app.models.save import ActiveRun, BattleSummary, DiscipleState, GameState, RunNode, RunPartySnapshot

MAX_PARTY = 6


def bond_bonus(party_ids: list[str], bonds: dict[str, dict]) -> dict[str, float]:
    """参考战力兼容属性资料；实际战斗羁绊由技能修正执行。"""
    active = set(party_ids)
    bonus: dict[str, float] = {}
    for bond in bonds.values():
        if len(active & set(bond["members"])) < bond.get("requires", len(bond["members"])):
            continue
        for effect in bond.get("effects", []):
            if effect["scope"] == "run" and effect["mode"] == "add_pct":
                bonus[effect["stat"]] = bonus.get(effect["stat"], 0) + effect["value"]
    return bonus


def affix_bonus(affix_ids: list[str], pool: list[dict]) -> dict[str, float]:
    by_id = {affix["id"]: affix for affix in pool}
    bonus: dict[str, float] = {}
    for affix_id in affix_ids:
        for effect in by_id.get(affix_id, {}).get("effects", []):
            if effect["scope"] == "run" and effect["mode"] == "add_pct":
                bonus[effect["stat"]] = bonus.get(effect["stat"], 0) + effect["value"]
    return bonus


def party_power(party: list[DiscipleState], templates: dict[str, dict], bonus: dict[str, float] | None = None) -> float:
    """只作为成长参考，不再据此判定战斗胜负。"""
    bonus = bonus or {}
    total = 0.0
    for disciple in party:
        base = templates[disciple.template_id]["base_stats"]
        growth = 1 + LEVEL_GROWTH * (disciple.level - 1) + REALM_GROWTH * (disciple.realm - 1)
        total += (
            base["atk"] * attack_multiplier(disciple.injury_stacks) * (1 + bonus.get("atk", 0))
            + base["def"] * .5 * (1 + bonus.get("def", 0)) + base["hp"] * .1 * (1 + bonus.get("hp", 0))
        ) * (growth + bonus.get("spd", 0) * .2)
    return total


def basic_skill(template_id: str, passive: bool = False) -> SkillDefinition:
    return SkillDefinition(id=f"{template_id}-{'passive' if passive else 'art'}", name="无常驻加成" if passive else "普通攻击", type="passive" if passive else "active")


def combatant(disciple: DiscipleState, template: dict, skills: dict[str, dict], bonuses: dict[str, float], slot: int) -> BattleUnit:
    """等级、伤势、宗门永久加成及自身常驻属性只在出发时应用一次。"""
    base = template["base_stats"]
    active = SkillDefinition.model_validate(skills[template["skill"]]) if template.get("skill") in skills else basic_skill(disciple.template_id)
    passive = SkillDefinition.model_validate(skills[template["passive"]]) if template.get("passive") in skills else basic_skill(disciple.template_id, True)
    growth = 1 + LEVEL_GROWTH * (disciple.level - 1) + REALM_GROWTH * (disciple.realm - 1)
    own = passive.bonuses if passive.condition == "always" else {}
    def value(stat: str) -> float:
        return base[stat] * (growth if stat != "spd" else 1) * (1 + bonuses.get(stat, 0) + own.get(stat, 0))
    return BattleUnit(
        id=disciple.id, template_id=disciple.template_id, name=template.get("name", disciple.template_id),
        asset_id=template.get("asset_id", ""), slot=slot,
        attack=value("atk") * attack_multiplier(disciple.injury_stacks), defense=value("def"),
        health=max(1, floor(value("hp"))), speed=value("spd"), active=active, passive=passive,
    )


def with_affixes(run: ActiveRun) -> list[BattleUnit]:
    bonus = affix_bonus(run.affixes, run.party_snapshot.affix_pool)
    return [unit.model_copy(update={
        "attack": max(1, unit.attack * (1 + bonus.get("atk", 0))),
        "defense": max(1, unit.defense * (1 + bonus.get("def", 0))),
        "health": max(1, floor(unit.health * (1 + bonus.get("hp", 0)))),
        "speed": max(1, unit.speed * (1 + bonus.get("spd", 0))),
    }) for unit in run.party_snapshot.combatants]


def enemy_power(step: int, mode: dict) -> int:
    return round(mode["base_enemy_power"] * (1 + step * mode["enemy_growth"]))


def node_reward(kind: str, mode: dict, step: int) -> dict[str, float]:
    base = mode["rewards"].get(kind, mode["rewards"]["battle"])
    scale = 1 + step * mode["reward_growth"]
    return {key: round(value * scale, 2) for key, value in base.items()}


def roll_choices(rng: Pcg32, step: int, mode: dict) -> list[RunNode]:
    is_boss = step >= mode["node_count"] - 1 or (step + 1) % mode["boss_every"] == 0
    nodes = []
    for _ in range(1 if is_boss else mode["choices_per_step"]):
        kind = "boss" if is_boss else "elite" if rng.randint(1, 100) <= mode["elite_chance"] else "battle"
        nodes.append(RunNode(kind=kind, enemy=f"{kind}_{step}", power=enemy_power(step, mode), reward=node_reward(kind, mode, step)))
    return nodes


def enemy_units(run: ActiveRun, node: RunNode) -> list[BattleUnit]:
    snapshot = run.party_snapshot
    scale = 1 + (len(run.nodes) - 1) * snapshot.mode["enemy_growth"]
    units = []
    for slot, enemy_id in enumerate(snapshot.mode["encounters"][node.kind]):
        enemy = snapshot.enemies[enemy_id]
        base = enemy.base_stats
        units.append(BattleUnit(
            id=f"enemy:{slot}:{enemy_id}", template_id=enemy_id, name=enemy.name, slot=slot,
            attack=base["atk"] * scale, defense=base["def"] * scale,
            health=max(1, floor(base["hp"] * scale)), speed=base["spd"],
            active=enemy.skill or basic_skill(enemy_id), passive=enemy.passive or basic_skill(enemy_id, True),
        ))
    return units


def run_status(run: ActiveRun, mode: dict | None = None) -> str:
    if run.end_reason in {"defeated", "round_limit"} or run.hp <= 0:
        return "defeated"
    if len(run.nodes) >= run.party_snapshot.mode["node_count"]:
        return "cleared"
    return "choosing_affix" if run.affix_pending else "choosing_node"


def start_run(
    state: GameState, party_ids: list[str], templates: dict[str, dict], mode: dict, now: datetime,
    seed: int | None = None, bonds: dict[str, dict] | None = None,
    skills: dict[str, dict] | None = None, enemies: dict[str, dict] | None = None,
    affix_pool: list[dict] | None = None,
) -> str | None:
    if state.active_run is not None:
        return "已有进行中的出征"
    if not party_ids or len(party_ids) > MAX_PARTY:
        return f"队伍需要 1 到 {MAX_PARTY} 名弟子"
    if len(set(party_ids)) != len(party_ids):
        return "队伍中有重复弟子"
    if state.resources.stamina < mode["stamina_cost"]:
        return "行动力不足"
    by_id = {disciple.id: disciple for disciple in state.disciples}
    duty_ids = {slot.disciple_id for slot in state.duty_slots}
    for disciple_id in party_ids:
        disciple = by_id.get(disciple_id)
        if disciple is None:
            return f"弟子 {disciple_id} 不存在"
        if disciple.busy:
            return f"弟子 {disciple_id} 正在出征"
        if disciple_id in duty_ids:
            return f"弟子 {disciple_id} 正在值守，请先撤下"
        if disciple.template_id not in templates:
            return f"弟子 {disciple_id} 模板未配置"
    members = set(by_id[key].template_id for key in party_ids)
    activated = [BattleBond.model_validate(bond) for bond in (bonds or {}).values()
                 if bond.get("modifiers") and len(members & set(bond["members"])) >= bond.get("requires", len(bond["members"]))]
    snapshot = RunPartySnapshot(
        combatants=tuple(combatant(by_id[key], templates[by_id[key].template_id], skills if skills is not None else load_skills(), state.bonuses, index) for index, key in enumerate(party_ids)),
        bonds=tuple(activated), mode=deepcopy(mode),
        enemies={key: EnemyDefinition.model_validate(value) for key, value in (enemies if enemies is not None else load_enemies()).items()},
        affix_pool=deepcopy(affix_pool if affix_pool is not None else load_affixes()),
    )
    run_seed = seed if seed is not None else secrets.randbits(63)
    rng = Pcg32(run_seed)
    hp = {unit.id: unit.health for unit in snapshot.combatants}
    state.active_run = ActiveRun(
        run_seed=run_seed, party=list(party_ids), mode=mode["id"], party_snapshot=snapshot,
        member_hp=hp, hp=sum(hp.values()), max_hp=sum(hp.values()),
        choices=roll_choices(rng, 0, snapshot.mode), started_at=now,
    )
    state.active_run.rng_cursor = rng.cursor
    state.resources.stamina -= mode["stamina_cost"]
    for key in party_ids:
        by_id[key].busy = True
    return None


def choose(state: GameState, choice_index: int, *_unused) -> str | None:
    run = state.active_run
    if run is None:
        return "没有进行中的出征"
    if run_status(run) in {"defeated", "cleared"}:
        return "出征已结束，请结算"
    if run.affix_pending:
        return "请先选择词条"
    if not 0 <= choice_index < len(run.choices):
        return "无效的节点选择"
    snapshot = run.party_snapshot
    mode = snapshot.mode
    node = run.choices[choice_index]
    run.nodes.append(node)
    run.choices = []
    allies = with_affixes(run)
    foes = enemy_units(run, node)
    hp_before = run.hp
    result = simulate_battle(allies, foes, run.member_hp, list(snapshot.bonds))
    run.member_hp = {unit.id: unit.hp for unit in result.final_units if unit.side == "ally"}
    run.hp = sum(run.member_hp.values())
    run.end_reason = result.reason if not result.won else None
    loot = node_reward(node.kind, mode, len(run.nodes) - 1) if result.won else {}
    run.last_battle = BattleSummary(
        id=f"{run.run_seed}:{len(run.nodes)}", party_power=round(sum(unit.attack + .5 * unit.defense + .1 * unit.health for unit in allies), 4),
        enemy_power=round(sum(unit.attack + .5 * unit.defense + .1 * unit.health for unit in foes)),
        hp_before=hp_before, hp_after=run.hp,
        damage=sum(effect.amount for event in result.events for effect in event.effects if effect.kind == "damage" and effect.target_id in run.member_hp),
        healed=sum(effect.amount for event in result.events for effect in event.effects if effect.kind == "heal" and effect.target_id in run.member_hp),
        won=result.won, loot=loot, node=node,
        rounds=result.rounds, reason=result.reason, initial_units=result.initial_units, final_units=result.final_units, events=result.events,
    )
    if not result.won:
        return None
    for key, value in loot.items():
        run.pending_loot[key] = run.pending_loot.get(key, 0) + value
    if len(run.nodes) >= mode["node_count"]:
        return None
    rng = Pcg32(run.run_seed)
    rng.advance_to(run.rng_cursor)
    if snapshot.affix_pool:
        groups = sorted({affix["group"] for affix in snapshot.affix_pool})
        group = pick_group(rng, groups, group_counts(run.affixes, snapshot.affix_pool))
        run.affix_options = draw(rng, [affix for affix in snapshot.affix_pool if affix["group"] == group], {})
        run.affix_pending = True
    else:
        run.choices = roll_choices(rng, len(run.nodes), mode)
    run.rng_cursor = rng.cursor
    return None


def group_counts(affix_ids: list[str], pool: list[dict]) -> dict[str, int]:
    groups = {affix["id"]: affix["group"] for affix in pool}
    return {group: sum(groups.get(key) == group for key in affix_ids) for group in set(groups.values())}


def pick_affix(state: GameState, affix_id: str, mode: dict | None = None) -> str | None:
    run = state.active_run
    if run is None:
        return "没有进行中的出征"
    if run.end_reason:
        return "出征已结束，请结算"
    if not run.affix_pending:
        return "当前没有待选词条"
    if affix_id not in run.affix_options:
        return "该词条不在候选中"
    before = {unit.id: unit.health for unit in with_affixes(run)}
    run.affixes.append(affix_id)
    after = with_affixes(run)
    for unit in after:
        run.member_hp[unit.id] = floor(run.member_hp[unit.id] * unit.health / before[unit.id])
    run.hp = sum(run.member_hp.values())
    run.max_hp = sum(unit.health for unit in after)
    run.affix_options = []
    run.affix_pending = False
    rng = Pcg32(run.run_seed)
    rng.advance_to(run.rng_cursor)
    run.choices = roll_choices(rng, len(run.nodes), run.party_snapshot.mode)
    run.rng_cursor = rng.cursor
    return None


def defeat_loot(pending: dict[str, float], cleared: int, mode: dict) -> dict[str, float]:
    loot = {key: round(value * mode["defeat_ratio"], 2) for key, value in pending.items()}
    for key, value in mode["defeat_floor_reward"].items():
        loot[key] = round(loot.get(key, 0) + value * cleared, 2)
    return loot


def settle_run(state: GameState, mode: dict, now: datetime) -> dict:
    run = state.active_run
    mode = run.party_snapshot.mode
    cleared = len(run.nodes)
    victory = run_status(run) == "cleared"
    loot = dict(run.pending_loot) if victory else defeat_loot(run.pending_loot, cleared, mode)
    for key, value in loot.items():
        if key in {"cultivation", "spirit_stone", "reputation", "stamina"}:
            setattr(state.resources, key, getattr(state.resources, key) + value)
        else:
            loot[key] = int(value)
            state.inventory[key] = state.inventory.get(key, 0) + int(value)
    state.tower_floor = max(state.tower_floor, cleared)
    for disciple in state.disciples:
        if disciple.id in run.party:
            disciple.busy = False
            if not victory:
                apply_injury(disciple, now)
    state.active_run = None
    return {"cleared": cleared, "victory": victory, "loot": loot}
