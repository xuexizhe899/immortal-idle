"""出征推进：固定定义、六人编队、自动战斗与一次性战利品结算。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from math import floor
import secrets

from app.config_loader import load_affixes, load_enemies, load_skills, load_weapons
from app.domain.affix import draw, pick_group
from app.domain.battle import simulate_battle
from app.domain.deployment import detach_for_run, restore_after_run
from app.domain.injuries import apply_injury, attack_multiplier
from app.domain.progression import LEVEL_GROWTH, REALM_GROWTH
from app.domain.rng import Pcg32
from app.domain.weapons import battle_bonuses, combat_bonuses
from app.models.battle import (
    AffixContribution, BattleBond, BattleUnit, ConditionalBonus, EnemyDefinition, SkillDefinition,
)
from app.models.save import ActiveRun, BattleReview, BattleSummary, DiscipleState, GameState, NpcSect, RunNode, RunPartySnapshot, RunReview

MAX_PARTY = 6
# 常驻修正的单键上限：同一键被多条道法叠加时截断，避免堆满一个乘区。
BONUS_CAP = {"damage": 0.20, "healing": 0.30, "shielding": 0.30, "taken_damage": 0.20}


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


def combatant(
    disciple: DiscipleState, template: dict, skills: dict[str, dict],
    bonuses: dict[str, float], slot: int,
    unit_bonuses: dict[str, float] | None = None,
) -> BattleUnit:
    """等级、伤势、个人/宗门永久加成及自身常驻属性只在出发时应用一次。"""
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
        bonuses=dict(unit_bonuses or {}),
    )


def with_affixes(run: ActiveRun) -> list[BattleUnit]:
    """把局内道法的属性、常驻修正与条件修正叠加到出发快照的副本上，不写回快照。"""
    pool = {affix["id"]: affix for affix in run.party_snapshot.affix_pool}
    attr: dict[str, float] = {}
    flat: dict[str, float] = {}
    conditional: list[ConditionalBonus] = []
    sources: list[dict] = []

    for affix_id in run.affixes:
        affix = pool.get(affix_id)
        if affix is None:
            continue
        source = {"id": affix_id, "name": affix.get("name", affix_id)}
        for effect in affix.get("effects") or []:
            if effect["scope"] == "run" and effect["mode"] == "add_pct":
                attr[effect["stat"]] = attr.get(effect["stat"], 0) + effect["value"]
                if effect["stat"] in {"atk", "def", "hp", "spd"} and effect["value"]:
                    sources.append({**source, "stat": effect["stat"], "value": effect["value"]})
        for key, value in (affix.get("bonuses") or {}).items():
            # 按领悟顺序分配同乘区额度，超过上限的部分不记作生效来源。
            previous = flat.get(key, 0)
            flat[key] = min(previous + value, BONUS_CAP.get(key, previous + value))
            if flat[key] > previous:
                sources.append({**source, "stat": key, "value": flat[key] - previous})
        for extra in affix.get("conditional") or []:
            conditional.append(ConditionalBonus.model_validate({
                **extra, "source_id": affix_id, "source_name": source["name"],
            }))

    def adjust(unit: BattleUnit) -> BattleUnit:
        bonuses = dict(unit.bonuses)
        for key, value in flat.items():
            bonuses[key] = bonuses.get(key, 0) + value
        return unit.model_copy(update={
            "attack": max(1, unit.attack * (1 + attr.get("atk", 0))),
            "defense": max(1, unit.defense * (1 + attr.get("def", 0))),
            "health": max(1, floor(unit.health * (1 + attr.get("hp", 0)))),
            "speed": max(1, unit.speed * (1 + attr.get("spd", 0))),
            "bonuses": bonuses,
            "conditional_bonuses": tuple(conditional),
            "affix_sources": tuple(AffixContribution(**source, unit_id=unit.id) for source in sources),
        })

    return [adjust(unit) for unit in run.party_snapshot.combatants]


def enemy_power(step: int, mode: dict, kind: str = "battle") -> int:
    multiplier = mode.get("kind_stat_multiplier", {}).get(kind, 1.0)
    return round(mode["base_enemy_power"] * (1 + step * mode["enemy_growth"]) * multiplier)


def encounter_roster(mode: dict, kind: str, step: int) -> list[str]:
    """按已走层数选择编成；旧快照无 variants 时回退到固定 encounters。"""
    variants = (mode.get("encounter_variants") or {}).get(kind)
    if variants:
        index = min(len(variants) - 1, step * len(variants) // max(1, mode["node_count"]))
        return variants[index]
    return mode["encounters"][kind]


def node_reward(kind: str, mode: dict, step: int) -> dict[str, float]:
    base = mode["rewards"].get(kind, mode["rewards"]["battle"])
    scale = 1 + step * mode["reward_growth"]
    return {key: round(value * scale, 2) for key, value in base.items()}


def roster_power(mode: dict, enemies: dict[str, EnemyDefinition], roster: list[str], step: int, kind: str) -> int:
    """计算候选编成的面板战力，和进入节点时的缩放公式保持一致。"""
    scale = 1 + step * mode["enemy_growth"]
    kind_scale = mode.get("kind_stat_multiplier", {}).get(kind, 1.0)
    total = 0.0
    for enemy_id in roster:
        enemy = enemies[enemy_id]
        passive = enemy.passive or basic_skill(enemy_id, True)
        bonuses = passive.bonuses if passive.condition == "always" else {}
        total += (
            enemy.base_stats["atk"] * scale * kind_scale * (1 + bonuses.get("atk", 0))
            + enemy.base_stats["def"] * scale * kind_scale * (1 + bonuses.get("def", 0)) * .5
            + max(1, floor(enemy.base_stats["hp"] * scale * kind_scale * (1 + bonuses.get("hp", 0)))) * .1
        )
    return round(total)


def route_reward(kind: str, mode: dict, step: int, power: int, baseline_power: int) -> dict[str, float]:
    """按面板战力缩放货币奖励，材料仍遵循原类型奖励。"""
    base = node_reward(kind, mode, step)
    if baseline_power <= 0:
        return base
    minimum = mode.get("route_reward_min", .85)
    maximum = mode.get("route_reward_max", 1.3)
    scale = min(max(power / baseline_power, minimum), maximum)
    return {
        key: round(value * scale, 2) if key in {"cultivation", "spirit_stone", "reputation"} else value
        for key, value in base.items()
    }


def roll_choices(rng: Pcg32, step: int, snapshot: RunPartySnapshot) -> list[RunNode]:
    """生成新路线候选；旧版本仍由 legacy_roll_choices 保持原随机顺序。"""
    mode = snapshot.mode
    if snapshot.route_version == 1:
        return legacy_roll_choices(rng, step, mode)

    is_boss = step >= mode["node_count"] - 1 or (step + 1) % mode["boss_every"] == 0
    nodes: list[RunNode] = []
    used: set[tuple[str, tuple[str, ...]]] = set()
    target_count = 1 if is_boss else mode["choices_per_step"]
    for index in range(target_count):
        kind = "boss" if is_boss else "elite" if rng.randint(1, 100) <= mode["elite_chance"] else "battle"
        variants = mode.get("encounter_variants", {}).get(kind) or [mode["encounters"][kind]]
        if is_boss:
            roster = list(variants[0])
        else:
            segment = min(len(variants) - 1, step * len(variants) // max(1, mode["node_count"]))
            pool = [list(item) for item in variants[max(0, segment - 1):segment + 1]]
            pool = [item for item in pool if (kind, tuple(item)) not in used]
            if not pool:
                continue
            roster = pool[rng.randint(0, len(pool) - 1)]
        identity = (kind, tuple(roster))
        if identity in used:
            continue
        used.add(identity)
        power = roster_power(mode, snapshot.enemies, roster, step, kind)
        baseline = roster_power(mode, snapshot.enemies, encounter_roster(mode, kind, step), step, kind)
        nodes.append(RunNode(
            kind=kind, enemy=f"{kind}_{step}_{index}", enemies=roster, power=power,
            reward=route_reward(kind, mode, step, power, baseline),
        ))
    return nodes


def legacy_roll_choices(rng: Pcg32, step: int, mode: dict) -> list[RunNode]:
    """旧路线候选：按历史顺序抽类型，不额外消费编成随机。"""
    is_boss = step >= mode["node_count"] - 1 or (step + 1) % mode["boss_every"] == 0
    nodes = []
    for _ in range(1 if is_boss else mode["choices_per_step"]):
        kind = "boss" if is_boss else "elite" if rng.randint(1, 100) <= mode["elite_chance"] else "battle"
        nodes.append(RunNode(kind=kind, enemy=f"{kind}_{step}", power=enemy_power(step, mode, kind), reward=node_reward(kind, mode, step)))
    return nodes


def enemy_units(run: ActiveRun, node: RunNode) -> list[BattleUnit]:
    """按当前层段编成创建敌人；精英/首领系数与常驻被动在创建时固化。"""
    snapshot = run.party_snapshot
    step = len(run.nodes) - 1
    scale = 1 + step * snapshot.mode["enemy_growth"]
    kind_scale = snapshot.mode.get("kind_stat_multiplier", {}).get(node.kind, 1.0)
    units = []
    roster = node.enemies or encounter_roster(snapshot.mode, node.kind, step)
    for slot, enemy_id in enumerate(roster):
        enemy = snapshot.enemies[enemy_id]
        base = enemy.base_stats
        passive = enemy.passive or basic_skill(enemy_id, True)
        own = passive.bonuses if passive.condition == "always" else {}
        units.append(BattleUnit(
            id=f"enemy:{slot}:{enemy_id}", template_id=enemy_id, name=enemy.name, slot=slot,
            attack=base["atk"] * scale * kind_scale * (1 + own.get("atk", 0)),
            defense=base["def"] * scale * kind_scale * (1 + own.get("def", 0)),
            health=max(1, floor(base["hp"] * scale * kind_scale * (1 + own.get("hp", 0)))),
            speed=base["spd"] * (1 + own.get("spd", 0)),
            active=enemy.skill or basic_skill(enemy_id), passive=passive,
        ))
    return units


def run_status(run: ActiveRun, mode: dict | None = None) -> str:
    if run.sect_id:
        if run.end_reason == "victory":
            return "cleared"
        return "defeated" if run.end_reason else "choosing_node"
    if run.end_reason in {"defeated", "round_limit"} or run.hp <= 0:
        return "defeated"
    if len(run.nodes) >= run.party_snapshot.mode["node_count"]:
        return "cleared"
    return "choosing_affix" if run.affix_pending else "choosing_node"


def start_run(
    state: GameState, party_ids: list[str], templates: dict[str, dict], mode: dict, now: datetime,
    seed: int | None = None, bonds: dict[str, dict] | None = None,
    skills: dict[str, dict] | None = None, enemies: dict[str, dict] | None = None,
    affix_pool: list[dict] | None = None, weapons: dict[str, dict] | None = None,
    route_version: int = 1, sect: NpcSect | None = None, tower_tier: int = 1,
) -> str | None:
    if route_version not in {1, 2}:
        return "不支持的路线版本"
    if state.active_run is not None:
        return "已有进行中的出征"
    if not party_ids or len(party_ids) > MAX_PARTY:
        return f"队伍需要 1 到 {MAX_PARTY} 名弟子"
    if len(set(party_ids)) != len(party_ids):
        return "队伍中有重复弟子"
    if sect is not None:
        if mode["id"] != "expedition" or not any(item.id == sect.id for item in state.sects):
            return "宗门目标不存在"
        if sect.conquered:
            return "该宗门已攻克，可安排驻守"
        if len(party_ids) < 3:
            return "宗门征讨需要 3 到 6 名随行弟子"
    if mode["id"] == "tower":
        if not 1 <= tower_tier <= min(3, state.facility_levels.get("tower", 1)):
            return "请先升级问道塔，开放对应塔阶"
        previous = max(state.tower_tiers.get(str(tower_tier - 1), 0), state.tower_floor if tower_tier == 2 else 0)
        if tower_tier > 1 and previous < 20:
            return "请先通关前一阶问道塔"
    if state.resources.stamina < mode["stamina_cost"]:
        return "行动力不足"
    by_id = {disciple.id: disciple for disciple in state.disciples}
    for disciple_id in party_ids:
        disciple = by_id.get(disciple_id)
        if disciple is None:
            return f"弟子 {disciple_id} 不存在"
        if disciple.busy:
            return f"弟子 {disciple_id} 正在出征"
        if disciple.template_id not in templates:
            return f"弟子 {disciple_id} 模板未配置"
    members = set(by_id[key].template_id for key in party_ids)
    weapon_map = weapons if weapons is not None else load_weapons()
    frozen_mode = deepcopy(mode)
    if sect is not None:
        # 征讨不生成问道路线，也不抽道法；守军、首胜奖励随本局一起固化。
        frozen_mode.update(node_count=4, sect=sect.model_dump(mode="json"))
    elif mode["id"] == "tower" and tower_tier > 1:
        frozen_mode["kind_stat_multiplier"] = {
            kind: mode.get("kind_stat_multiplier", {}).get(kind, 1) * (1 + .6 * (tower_tier - 1))
            for kind in ("battle", "elite", "boss")
        }
        frozen_mode["rewards"] = {
            kind: {key: value * (1 + .5 * (tower_tier - 1)) for key, value in rewards.items()}
            for kind, rewards in mode["rewards"].items()
        }
    activated = [BattleBond.model_validate(bond) for bond in (bonds or {}).values()
                 if bond.get("modifiers") and len(members & set(bond["members"])) >= bond.get("requires", len(bond["members"]))]
    snapshot = RunPartySnapshot(
        combatants=tuple(
            combatant(
                by_id[key], templates[by_id[key].template_id],
                skills if skills is not None else load_skills(),
                combat_bonuses(by_id[key], state.bonuses, weapon_map, state.weapon_levels), index,
                battle_bonuses(by_id[key], weapon_map, state.weapon_levels),
            )
            for index, key in enumerate(party_ids)
        ),
        bonds=tuple(activated), mode=frozen_mode,
        enemies={key: EnemyDefinition.model_validate(value) for key, value in (enemies if enemies is not None else load_enemies()).items()},
        affix_pool=[] if sect is not None else deepcopy(affix_pool if affix_pool is not None else load_affixes()),
        route_version=route_version,
    )
    run_seed = seed if seed is not None else secrets.randbits(63)
    rng = Pcg32(run_seed)
    hp = {unit.id: unit.health for unit in snapshot.combatants}
    state.active_run = ActiveRun(
        run_seed=run_seed, party=list(party_ids), mode=mode["id"], party_snapshot=snapshot,
        member_hp=hp, hp=sum(hp.values()), max_hp=sum(hp.values()),
        choices=[] if sect is not None else roll_choices(rng, 0, snapshot), started_at=now,
        sect_id=sect.id if sect is not None else None, tower_tier=tower_tier,
        return_posts=detach_for_run(state, party_ids),
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
    if run.sect_id:
        return "请为本场擂台选择三名弟子"
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
    loot = (
        dict(node.reward)
        if result.won and (node.reward or snapshot.route_version >= 2)
        else node_reward(node.kind, mode, len(run.nodes) - 1) if result.won else {}
    )
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
    owned = set(run.affixes)
    available = [affix for affix in snapshot.affix_pool if affix["id"] not in owned]
    if available:
        groups = sorted({affix["group"] for affix in available})
        group = pick_group(rng, groups, group_counts(run.affixes, snapshot.affix_pool))
        options = draw(rng, [affix for affix in available if affix["group"] == group], {})
        if len(options) < 3:
            rest = [affix for affix in available if affix["id"] not in options]
            options += draw(rng, rest, {}, 3 - len(options))
        run.affix_options = options
        run.affix_pending = True
    else:
        run.choices = roll_choices(rng, len(run.nodes), snapshot)
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
    run.choices = roll_choices(rng, len(run.nodes), run.party_snapshot)
    run.rng_cursor = rng.cursor
    return None


def defeat_loot(pending: dict[str, float], cleared: int, mode: dict) -> dict[str, float]:
    loot = {key: round(value * mode["defeat_ratio"], 2) for key, value in pending.items()}
    for key, value in mode["defeat_floor_reward"].items():
        loot[key] = round(loot.get(key, 0) + value * cleared, 2)
    return loot


def build_battle_review(summary: BattleSummary) -> BattleReview:
    """从最后一战的服务端快照提炼有限事实，不根据当前配置重建历史。"""
    previous_hp = {unit.id: unit.hp for unit in summary.initial_units}
    ally_ids = {unit.id for unit in summary.initial_units if unit.side == "ally"}
    first_down_id = None
    first_down_name = None
    candidates: list[dict[str, str | int]] = []
    for event in summary.events:
        units = {unit.id: unit for unit in event.units}
        if first_down_id is None:
            for unit in event.units:
                if unit.side == "ally" and previous_hp.get(unit.id, unit.hp) > 0 and unit.hp <= 0:
                    first_down_id, first_down_name = unit.id, unit.name
                    break
        previous_hp.update({unit.id: unit.hp for unit in event.units})
        actor = units.get(event.actor_id)
        for effect in event.effects:
            if effect.kind != "damage" or effect.amount <= 0:
                continue
            target = units.get(effect.target_id)
            candidates.append({
                "sequence": event.sequence, "round": event.round,
                "actor_id": event.actor_id, "actor_name": actor.name if actor else event.actor_id,
                "skill_name": event.skill_name, "target_id": effect.target_id,
                "target_name": target.name if target else effect.target_id,
                "amount": effect.amount,
            })
    candidates.sort(key=lambda item: (-int(item["amount"]), int(item["sequence"]), str(item["target_id"])))
    # 保护指标只统计我方收到的增量与吸收；旧战报缺行动或单位来源时保留未记录。
    ally_effects = [
        effect for event in summary.events for effect in event.effects
        if effect.target_id in ally_ids
    ]
    has_protection_records = bool(summary.events and ally_ids)
    return BattleReview(
        node=summary.node, party_power=summary.party_power, enemy_power=summary.enemy_power,
        hp_before=summary.hp_before, hp_after=summary.hp_after, damage=summary.damage,
        healed=summary.healed,
        shield_applied=sum(effect.amount for effect in ally_effects if effect.kind == "shield") if has_protection_records else None,
        shield_absorbed=sum(effect.absorbed for effect in ally_effects if effect.kind == "damage") if has_protection_records else None,
        won=summary.won, rounds=summary.rounds, reason=summary.reason,
        first_down_id=first_down_id, first_down_name=first_down_name,
        surviving_enemies=[unit for unit in summary.final_units if unit.side == "enemy" and unit.hp > 0][:6],
        key_actions=candidates[:3],
    )


def settle_run(state: GameState, mode: dict, now: datetime) -> dict:
    run = state.active_run
    mode = run.party_snapshot.mode
    cleared = len(run.nodes)
    victory = run_status(run) == "cleared"
    if run.sect_id:
        target = next(item for item in state.sects if item.id == run.sect_id)
        loot = dict(run.pending_loot) if victory and not target.conquered else {}
        if victory:
            target.conquered = True
    else:
        loot = dict(run.pending_loot) if victory else defeat_loot(run.pending_loot, cleared, mode)
    for key, value in loot.items():
        if key in {"cultivation", "spirit_stone", "reputation", "stamina"}:
            setattr(state.resources, key, getattr(state.resources, key) + value)
        else:
            loot[key] = int(value)
            state.inventory[key] = state.inventory.get(key, 0) + int(value)
    # 出征清档前保留终止原因、到达节点和最后一场的关键指标，便于下一次整备时针对性调整。
    last_battle = run.last_battle
    state.last_run_review = RunReview(
        mode=run.mode, cleared=cleared, total_nodes=cleared if run.sect_id and victory else mode["node_count"], victory=victory,
        sect_id=run.sect_id, sect_name=mode["sect"]["name"] if run.sect_id else None,
        tower_tier=run.tower_tier,
        end_reason=run.end_reason,
        loot=loot,
        last_battle=build_battle_review(last_battle) if last_battle else None,
    )
    if run.mode == "expedition" and not run.sect_id:
        state.expedition_floor = max(state.expedition_floor, cleared)
    elif run.mode == "tower":
        previous_floor = state.tower_floor if run.tower_tier == 1 else 0
        # 失败节点只是到达，不能算通关；尤其第20层失败不能解锁下一塔阶。
        completed = cleared - int(last_battle is not None and not last_battle.won)
        state.tower_floor = max(state.tower_floor, completed)
        tier = str(run.tower_tier)
        state.tower_tiers[tier] = max(state.tower_tiers.get(tier, 0), previous_floor, completed)
    for disciple in state.disciples:
        if disciple.id in run.party:
            disciple.busy = False
            if not victory and (not run.sect_id or disciple.id in run.deployed):
                apply_injury(disciple, now)
    missing = restore_after_run(state, run.return_posts, now)
    if missing:
        names = [next((unit.name for unit in run.party_snapshot.combatants if unit.id == key), key) for key in missing]
        state.logs.append(f"原岗位已满，未自动回岗：{'、'.join(names)}")
    state.active_run = None
    return {"cleared": cleared, "victory": victory, "loot": loot}
