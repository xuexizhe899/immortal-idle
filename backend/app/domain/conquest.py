"""宗门生成与擂台征讨；身份持久保存，战斗只读取本局快照。"""

from __future__ import annotations

from math import floor

from app.domain.battle import simulate_battle
from app.domain.rng import Pcg32
from app.models.battle import BattleUnit, EnemyDefinition, SkillDefinition
from app.models.save import BattleSummary, GameState, NpcSect, RunNode

GUARD_DAMAGE = {3: 50, 2: 30, 1: 15}


def _sect_unit(definition: dict, identity: str, name: str, slot: int, scale: float, leader: bool = False) -> BattleUnit:
    enemy = EnemyDefinition.model_validate(definition)
    passive = enemy.passive or SkillDefinition(id=f"{enemy.id}-passive", name="无常驻加成", type="passive")
    active = enemy.skill or SkillDefinition(id=f"{enemy.id}-art", name="普通攻击", type="active")
    own = passive.bonuses if passive.condition == "always" else {}
    base = enemy.base_stats
    return BattleUnit(
        id=identity, template_id=enemy.id, name=name, slot=slot, asset_id=enemy.asset_id,
        attack=base["atk"] * scale * (1.55 if leader else 1) * (1 + own.get("atk", 0)),
        defense=base["def"] * scale * (1.35 if leader else 1) * (1 + own.get("def", 0)),
        health=max(1, floor(base["hp"] * scale * (3.2 if leader else 1) * (1 + own.get("hp", 0)))),
        speed=base["spd"] * (1 + own.get("spd", 0)), active=active, passive=passive,
    )


def ensure_sects(state: GameState, config: dict, enemies: dict[str, dict]) -> bool:
    """每级补齐三座宗门；按编号独立播种，扩图不会重抽已生成的身份与守军。"""
    changed = False
    hall_level = min(3, max(1, state.facility_levels.get("hall", 1)))
    existing = {sect.id for sect in state.sects}
    for index in range(hall_level * 3):
        identity = f"sect_{index + 1}"
        if identity in existing:
            continue
        rng = Pcg32(state.rng_seed + 104729 * (index + 1))
        level = index // 3 + 1
        style = config["styles"][index % 3]
        prefix = rng.pick(config["name_prefixes"])
        name = f"{prefix}{style['suffix']}·{config['level_names'][level - 1]}"
        material = style["materials"][level - 1]
        scale = config["level_scales"][level - 1]
        teams = []
        for round_index in range(3):
            roster = style["teams"][rng.randint(0, len(style["teams"]) - 1)]
            teams.append([
                _sect_unit(enemies[enemy_id], f"{identity}:arena:{round_index}:{slot}",
                           f"{style['name']}弟子·{slot + 1}", slot, scale * (1 + round_index * .08))
                for slot, enemy_id in enumerate(roster)
            ])
        leader = _sect_unit(enemies[style["leader"]], f"{identity}:leader", f"{prefix}宗主", 0, scale, True)
        state.sects.append(NpcSect(
            id=identity, name=name, level=level, style=style["name"],
            material_id=material, special_material_id=style["special_material"],
            arena_teams=teams, leader=leader,
            loot={"cultivation": 40 * level, "spirit_stone": 30 * level,
                  "reputation": 60 * level, material: 8 * level, style["special_material"]: 3 * level},
        ))
        changed = True
    return changed


def arena(state: GameState, party_ids: list[str]) -> str | None:
    """每场仅三名随行弟子上阵；落败的擂台不会替尚存的替补判定整局失败。"""
    run = state.active_run
    if run is None or not run.sect_id:
        return "没有进行中的宗门征讨"
    if run.end_reason is not None:
        return "征讨已结束，请结算"
    if len(party_ids) != 3 or len(set(party_ids)) != 3:
        return "每场擂台需要三名不同的弟子"
    if any(key not in run.party or run.member_hp.get(key, 0) <= 0 for key in party_ids):
        return "只能选择本次随行且尚未倒下的弟子"
    sect = NpcSect.model_validate(run.party_snapshot.mode["sect"])
    is_boss = run.guard == 0
    foes = [sect.leader] if is_boss else sect.arena_teams[run.arena_round]
    by_id = {unit.id: unit for unit in run.party_snapshot.combatants}
    allies = [by_id[key].model_copy(update={"slot": slot}) for slot, key in enumerate(party_ids)]
    templates = {unit.template_id for unit in allies}
    # 羁绊按本场三名上阵弟子触发，替补不能隔空提供羁绊。
    bonds = [bond for bond in run.party_snapshot.bonds if len(templates & set(bond.members)) >= bond.requires]
    hp_before = sum(run.member_hp[key] for key in party_ids)
    result = simulate_battle(allies, foes, run.member_hp, bonds)
    run.selected_party = list(party_ids)
    run.deployed = list(dict.fromkeys([*run.deployed, *party_ids]))
    for unit in result.final_units:
        if unit.side == "ally":
            run.member_hp[unit.id] = unit.hp
    run.hp = sum(run.member_hp.values())
    if not is_boss:
        run.arena_round += 1
        survivors = sum(unit.side == "ally" and unit.hp > 0 for unit in result.final_units)
        if result.won:
            run.guard = max(0, run.guard - GUARD_DAMAGE.get(survivors, 0))
    loot = dict(sect.loot) if is_boss and result.won else {}
    node = RunNode(kind="boss" if is_boss else "battle", enemy=f"{sect.name}·{'宗主' if is_boss else '擂台'}",
                   enemies=[unit.template_id for unit in foes],
                   power=round(sum(unit.attack + .5 * unit.defense + .1 * unit.health for unit in foes)), reward=loot)
    run.nodes.append(node)
    run.last_battle = BattleSummary(
        id=f"{run.run_seed}:{len(run.nodes)}", node=node, enemy_power=node.power,
        party_power=round(sum(unit.attack + .5 * unit.defense + .1 * unit.health for unit in allies), 4),
        hp_before=hp_before, hp_after=sum(run.member_hp[key] for key in party_ids),
        damage=sum(effect.amount for event in result.events for effect in event.effects if effect.kind == "damage" and effect.target_id in party_ids),
        healed=sum(effect.amount for event in result.events for effect in event.effects if effect.kind == "heal" and effect.target_id in party_ids),
        won=result.won, loot=loot, rounds=result.rounds, reason=result.reason,
        initial_units=result.initial_units, final_units=result.final_units, events=result.events,
    )
    if is_boss:
        run.end_reason = "victory" if result.won else result.reason
        run.pending_loot = loot
    elif sum(hp > 0 for hp in run.member_hp.values()) < 3:
        run.end_reason = "insufficient_fighters"
    elif run.arena_round >= 3 and run.guard > 0:
        run.end_reason = "guard_unbroken"
    return None


def retreat(state: GameState) -> str | None:
    run = state.active_run
    if run is None or not run.sect_id:
        return "没有进行中的宗门征讨"
    if run.end_reason is not None:
        return "征讨已结束，请结算"
    run.end_reason = "retreated"
    run.pending_loot = {}
    return None
