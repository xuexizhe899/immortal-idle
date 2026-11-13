"""有限回合自动战斗。输入均为固化定义，输出真实状态与逐行动战报。"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import floor

from app.models.battle import (
    BattleAction, BattleBond, BattleEffectResult, BattleEvent, BattleStatus,
    BattleUnit, BattleUnitState,
)

ROUND_LIMIT = 20
# 条件修正的单键上限：多条条件道法同时满足时截断，避免条件叠满。
CONDITIONAL_CAP = {"damage": 0.35, "healing": 0.20, "shielding": 0.20, "taken_damage": 0.15}


@dataclass
class Unit:
    definition: BattleUnit
    side: str
    hp: int
    turns: int = 0
    next_active: int = 1
    statuses: list[BattleStatus] = field(default_factory=list)

    @property
    def shield(self) -> int:
        return sum(status.remaining for status in self.statuses if status.kind == "shield")

    def stat(self, name: str) -> float:
        base = {"atk": self.definition.attack, "def": self.definition.defense, "spd": self.definition.speed}[name]
        bonus = sum(status.value for status in self.statuses if status.kind == "buff" and status.stat == name)
        return max(1, base * (1 + min(1, max(-.5, bonus))))

    def view(self) -> BattleUnitState:
        return BattleUnitState(
            id=self.definition.id, template_id=self.definition.template_id,
            name=self.definition.name, side=self.side, slot=self.definition.slot,
            asset_id=self.definition.asset_id, hp=self.hp, max_hp=self.definition.health,
            shield=self.shield, attack=self.stat("atk"), defense=self.stat("def"), speed=self.stat("spd"),
            cooldown=max(0, self.next_active - self.turns - 1),
            statuses=[status.model_copy(deep=True) for status in self.statuses],
        )


@dataclass
class BattleOutcome:
    won: bool
    reason: str
    rounds: int
    initial_units: list[BattleUnitState]
    final_units: list[BattleUnitState]
    events: list[BattleEvent]


def condition_matches(condition: str, actor: Unit, target: Unit | None, round_no: int, weakened: set[str], shielded: bool) -> bool:
    """条件只看本次行动开始时的状态，不追溯触发刚施加的降防。"""
    if condition == "always":
        return True
    if condition == "shielded":
        return shielded
    if condition == "first_round":
        return round_no == 1
    if condition == "target_weakened":
        return target is not None and target.definition.id in weakened
    if condition == "target_wounded":
        return target is not None and target.hp * 2 < target.definition.health
    if condition == "low_hp":
        return actor.hp * 2 < actor.definition.health
    return False


def targets_for(action: BattleAction, actor: Unit, units: list[Unit]) -> list[Unit]:
    friendly = not action.target.startswith("enemy") and action.target != "all_enemies"
    candidates = [unit for unit in units if unit.hp > 0 and (unit.side == actor.side) == friendly]
    if action.target == "self":
        candidates = [actor]
    elif action.target == "ally_template":
        candidates = [unit for unit in candidates if unit.definition.template_id == action.target_template]
    if action.kind == "heal":
        candidates = [unit for unit in candidates if unit.hp < unit.definition.health]
    elif action.kind == "shield":
        candidates = [unit for unit in candidates if unit.shield < unit.definition.health]
    if action.target in {"ally_lowest", "enemy_lowest"}:
        candidates.sort(key=lambda unit: (unit.hp / unit.definition.health, unit.definition.slot))
    else:
        candidates.sort(key=lambda unit: unit.definition.slot)
    return candidates[:action.count]


def total_bonus(
    unit: Unit,
    passive_bonus: dict[str, float],
    context: tuple[Unit | None, int, set[str], bool] | None = None,
) -> dict[str, float]:
    """专武、被动与条件道法的乘区相加，不互相覆盖；减伤不进入攻击加成。"""
    total = dict(unit.definition.bonuses)
    for stat, value in passive_bonus.items():
        total[stat] = total.get(stat, 0.0) + value

    if context is None:
        return total

    target, round_no, weakened, shielded = context
    conditional_total: dict[str, float] = {}
    for extra in unit.definition.conditional_bonuses:
        if not condition_matches(extra.condition, unit, target, round_no, weakened, shielded):
            continue
        for stat, value in extra.bonuses.items():
            conditional_total[stat] = conditional_total.get(stat, 0.0) + value

    for stat, value in conditional_total.items():
        if stat == "taken_damage":
            continue
        total[stat] = total.get(stat, 0.0) + min(value, CONDITIONAL_CAP.get(stat, value))
    return total


def damage_reduction(target: Unit, round_no: int) -> float:
    """受击方减伤：常驻加自身状态条件，条件部分单键截断，合计最多 30%。"""
    flat = target.definition.bonuses.get("taken_damage", 0.0)
    shielded = target.shield > 0
    conditional = 0.0
    for extra in target.definition.conditional_bonuses:
        value = extra.bonuses.get("taken_damage", 0.0)
        if value and condition_matches(extra.condition, target, None, round_no, set(), shielded):
            conditional += value
    conditional = min(conditional, CONDITIONAL_CAP["taken_damage"])
    return min(0.3, max(0.0, flat + conditional))


def has_effect(action: BattleAction, actor: Unit, target: Unit, source: str, bonus: dict[str, float]) -> bool:
    if action.kind != "shield":
        return True
    previous = next((status.remaining for status in target.statuses if status.source == source and status.kind == "shield"), 0)
    proposed = floor(actor.stat("atk") * action.coefficient * (1 + bonus.get("shielding", 0)))
    return proposed > previous and target.shield < target.definition.health


def apply_effect(action: BattleAction, actor: Unit, target: Unit, round_no: int, source: str, bonus: dict[str, float]) -> BattleEffectResult:
    amount = absorbed = 0
    if action.kind == "damage":
        reduction = damage_reduction(target, round_no)
        damage = max(1, floor(actor.stat("atk") * action.coefficient * (1 + bonus.get("damage", 0)) * (1 - reduction) * 100 / (100 + target.stat("def"))))
        for status in target.statuses:
            if status.kind != "shield":
                continue
            used = min(status.remaining, damage)
            status.remaining -= used
            absorbed += used
            damage -= used
        target.statuses = [status for status in target.statuses if status.kind != "shield" or status.remaining > 0]
        amount = min(target.hp, damage)
        target.hp -= amount
    elif action.kind == "heal":
        amount = min(target.definition.health - target.hp, floor(actor.stat("atk") * action.coefficient * (1 + bonus.get("healing", 0))))
        target.hp += amount
    elif action.kind == "shield":
        existing = next((status for status in target.statuses if status.source == source and status.kind == "shield"), None)
        previous = existing.remaining if existing else 0
        proposed = floor(actor.stat("atk") * action.coefficient * (1 + bonus.get("shielding", 0)))
        allowed = target.definition.health - target.shield + previous
        replacement = min(allowed, max(previous, proposed))
        amount = replacement - previous
        if amount > 0:
            if existing:
                target.statuses.remove(existing)
            target.statuses.append(BattleStatus(source=source, kind="shield", remaining=replacement, expires_round=round_no + action.duration))
    else:
        target.statuses = [status for status in target.statuses if not (status.source == source and status.kind == "buff" and status.stat == action.stat)]
        target.statuses.append(BattleStatus(source=source, kind="buff", stat=action.stat, value=action.value, expires_round=round_no + action.duration))
    return BattleEffectResult(
        target_id=target.definition.id, kind=action.kind, amount=amount, absorbed=absorbed,
        hp_after=target.hp, shield_after=target.shield, stat=action.stat if action.kind == "buff" else "",
        value=action.value if action.kind == "buff" else 0, source=source,
    )


def simulate_battle(allies: list[BattleUnit], enemies: list[BattleUnit], member_hp: dict[str, int], bonds: list[BattleBond] | None = None) -> BattleOutcome:
    """单场最多 12×20 次主行动，不读取时钟、不消费随机数、不写永久层。"""
    if not 1 <= len(allies) <= 6 or not 1 <= len(enemies) <= 6:
        raise ValueError("交战双方均需要 1–6 个单位")
    units = [Unit(unit, "ally", max(0, min(unit.health, member_hp.get(unit.id, unit.health)))) for unit in allies]
    units += [Unit(unit, "enemy", unit.health) for unit in enemies]
    initial = [unit.view() for unit in units]
    events: list[BattleEvent] = []
    reason = "round_limit"
    round_no = 0
    for round_no in range(1, ROUND_LIMIT + 1):
        for unit in units:
            unit.statuses = [status for status in unit.statuses if status.expires_round > round_no]
        order = sorted(units, key=lambda unit: (-unit.stat("spd"), unit.side != "ally", unit.definition.slot))
        for actor in order:
            if not any(unit.hp > 0 and unit.side == "ally" for unit in units):
                reason = "defeated"
                break
            if not any(unit.hp > 0 and unit.side == "enemy" for unit in units):
                reason = "victory"
                break
            if actor.hp <= 0:
                continue
            actor.turns += 1
            active = actor.definition.active
            weakened = {unit.definition.id for unit in units if any(status.kind == "buff" and status.stat == "def" and status.value < 0 for status in unit.statuses)}
            shielded = actor.shield > 0
            passive = actor.definition.passive
            use_active = actor.turns >= actor.next_active and any(
                has_effect(action, actor, target, f"{actor.definition.id}:{active.id}:{index}",
                           total_bonus(actor, passive.bonuses if condition_matches(passive.condition, actor, target, round_no, weakened, shielded) else {},
                                       (target, round_no, weakened, shielded)))
                for index, action in enumerate(active.actions) for target in targets_for(action, actor, units)
            )
            skill_id = active.id if use_active else "basic_attack"
            skill_name = active.name if use_active else "普通攻击"
            actions = [(action.model_copy(deep=True), skill_id) for action in active.actions] if use_active else [(BattleAction(kind="damage", target="enemy_first"), "basic_attack")]
            first_target = next((target for action, _ in actions if action.kind == "damage" for target in targets_for(action, actor, units)), None)
            triggered: list[str] = []
            if use_active:
                actor.next_active = actor.turns + active.cooldown
                for bond in bonds or []:
                    if actor.side != "ally" or actor.definition.template_id not in bond.members:
                        continue
                    for modifier in bond.modifiers:
                        if modifier.skill != active.id or not condition_matches(modifier.condition, actor, first_target, round_no, weakened, shielded):
                            continue
                        triggered.append(bond.id)
                        for action, _ in actions:
                            action.count = min(6, action.count + modifier.add_targets)
                            action.coefficient *= 1 + modifier.coefficient_bonus
                            action.duration = min(20, action.duration + modifier.duration_bonus)
                        actions += [(action.model_copy(deep=True), bond.id) for action in modifier.extra_actions]
            if len(actions) > 4:
                raise ValueError("联动后的技能最多包含 4 条效果")
            effects: list[BattleEffectResult] = []
            # 目标随本次施法固化：前一条效果击倒目标时，后续效果跳过，不转移。
            selected_targets = [targets_for(action, actor, units) for action, _ in actions]
            for index, ((action, origin), targets) in enumerate(zip(actions, selected_targets)):
                for target in targets:
                    if target.hp <= 0:
                        continue
                    bonus = total_bonus(actor, passive.bonuses if condition_matches(passive.condition, actor, target, round_no, weakened, shielded) else {},
                                        (target, round_no, weakened, shielded))
                    effects.append(apply_effect(action, actor, target, round_no, f"{actor.definition.id}:{origin}:{index}", bonus))
            events.append(BattleEvent(
                sequence=len(events) + 1, round=round_no, actor_id=actor.definition.id,
                skill_id=skill_id, skill_name=skill_name, vfx=active.vfx if use_active else "strike",
                bonds=sorted(set(triggered)), effects=effects, units=[unit.view() for unit in units],
            ))
        if reason != "round_limit":
            break
        if not any(unit.hp > 0 and unit.side == "enemy" for unit in units):
            reason = "victory"
            break
        if not any(unit.hp > 0 and unit.side == "ally" for unit in units):
            reason = "defeated"
            break
    return BattleOutcome(reason == "victory", reason, round_no, initial, [unit.view() for unit in units], events)
