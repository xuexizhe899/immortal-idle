"""用真实领域规则测量新档到首区令牌的进程，不访问数据库或用户存档。

运行：backend/.venv/Scripts/python.exe tools/simulate_world_progression.py
所有操作时长是可审查的预算假设，不是人工游玩时长或体验验收。
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config_loader import (  # noqa: E402
    load_affixes, load_bonds, load_disciples, load_enemies, load_equipment,
    load_facilities, load_modes, load_recipes, load_sects, load_skills, load_weapons, load_world,
)
from app.domain import conquest, duty, equipment, progression, recruit, run_engine, world  # noqa: E402
from app.domain.deployment import assign_garrison  # noqa: E402
from app.domain.facilities import facility_views, upgrade_facility  # noqa: E402
from app.domain.items import heal_party, heal_party_preview  # noqa: E402
from app.domain.rng import Pcg32  # noqa: E402
from app.domain.settle import settle  # noqa: E402
from app.domain.weapons import combat_bonuses  # noqa: E402

START = datetime(2026, 11, 19, tzinfo=timezone.utc)
# 500声望能先招募白素贞、华佗、杜甫、精卫，余下声望必须实际战斗获得。
ROSTER = ("baisuzhen", "huatuo", "dufu", "jingwei", "houyi", "zhugeliang")
STAT_WEIGHT = {"atk": 1, "hp": .9, "def": .8, "spd": .5, "damage": 1.1, "healing": 1, "shielding": .8}
SCENARIOS = {
    "map_30m": {"sessions": 2, "minutes": 30, "tower_first": False},
    "map_60m": {"sessions": 2, "minutes": 60, "tower_first": False},
    "tower_60m": {"sessions": 2, "minutes": 60, "tower_first": True},
    "idle_10m": {"sessions": 1, "minutes": 10, "tower_first": False},
}
PROFILES = {"formal": {"source": "当前正式配置，不叠加实验倍率"}}


class Simulation:
    def __init__(self, seed: int, scenario: str, profile: str = "formal"):
        self.seed, self.scenario = seed, scenario
        self.policy = SCENARIOS[scenario]
        self.state = progression.new_game_state()
        self.state.rng_seed = seed
        self.state.equipment_version = 1
        self.now = self.last_settled = START
        self.scheduler = Pcg32(seed + 104729)
        self.templates, self.skills = load_disciples(), load_skills()
        self.bonds, self.enemies = load_bonds(), load_enemies()
        self.profile = profile
        self.world, self.gear_rules = deepcopy(load_world()), load_equipment()
        self.facilities, self.recipes = load_facilities(), load_recipes()
        self.modes, self.weapons = deepcopy(load_modes()), load_weapons()
        if profile != "formal":
            raise ValueError("最终复现只接受 formal，直接使用当前正式配置")
        self.affixes = load_affixes()
        self.ledger = Counter()
        self.runs, self.daily, self.recruited = [], [], []
        self.attempted_this_session = set()
        self.failed_inputs = {}
        self.first_token = self.first_24_slots = self.first_six = None
        self.first_clear_state = None
        self.day7_state = None
        self.budget = 0.0
        self.towers_in_session = 0
        self.dungeons_in_session = 0
        conquest.ensure_sects(self.state, load_sects(), self.enemies, self.world)
        world.ensure_world(self.state, self.now, self.world)

    def elapsed(self):
        return round((self.now - START).total_seconds() / 3600, 4)

    def tick(self, seconds: float = 0, target: datetime | None = None):
        duty.record_event(self.state, self.templates, self.now, self.bonds)
        following = max(self.now, target) if target is not None else self.now + timedelta(seconds=seconds)
        report = settle(self.state, self.last_settled, following)
        self.ledger["idle_cultivation"] += report.cultivation
        self.ledger["idle_spirit_stone"] += report.spirit_stone
        self.ledger["stamina_recovered"] += report.stamina
        self.ledger["idle_hours_dropped"] += report.dropped_hours
        self.ledger["idle_gear_material"] += report.materials.get("lian_qi_jing_cui", 0)
        self.now = self.last_settled = following
        world.ensure_world(self.state, self.now, self.world)
        self.budget -= seconds
        self.ledger["active_seconds_estimate"] += seconds

    def party(self):
        return [disciple.id for disciple in self.state.disciples[:6]]

    def score(self):
        total = 0.0
        for index, disciple in enumerate(self.state.disciples[:6]):
            bonuses = combat_bonuses(disciple, self.state.bonuses, self.weapons, self.state.weapon_levels)
            for key, value in equipment.combat_equipment_bonuses(self.state, disciple).items():
                bonuses[key] = bonuses.get(key, 0) + value
            unit = run_engine.combatant(disciple, self.templates[disciple.template_id], self.skills, bonuses, index)
            total += unit.attack + .5 * unit.defense + .1 * unit.health
        return total

    @staticmethod
    def gear_score(item):
        return sum(value * STAT_WEIGHT.get(key, .5) for key, value in equipment.equipment_stats(item).items())

    def prepare_party(self):
        for identity in ROSTER:
            if identity in self.state.unlocks:
                continue
            cost = self.templates[identity]["unlock_cost"]["reputation"]
            if self.state.resources.reputation < cost or self.budget < 5:
                break
            self.tick(5)
            error = recruit.recruit(self.state, identity, self.templates)
            if error:
                raise RuntimeError(error)
            self.recruited.append({"id": identity, "cost": cost, "hours": self.elapsed()})
            if len(self.party()) == 6 and self.first_six is None:
                self.first_six = self.elapsed()
        # 先把新装备给空槽和较弱槽，不预知随机结果，也不复制同一实例。
        owned = {key for disciple in self.state.disciples for key in disciple.gear_slots.values()}
        for item in sorted(self.state.gear.values(), key=self.gear_score, reverse=True):
            if item.id in owned or self.budget < 4:
                continue
            target = min(self.state.disciples, key=lambda disciple: self.gear_score(self.state.gear[disciple.gear_slots[item.slot]]) if item.slot in disciple.gear_slots else -1)
            previous = self.state.gear.get(target.gear_slots.get(item.slot, ""))
            if previous and self.gear_score(previous) >= self.gear_score(item):
                continue
            self.tick(4)
            if equipment.equip_gear(self.state, item.id, target.id):
                raise RuntimeError("模拟换装校验失败")
            owned.add(item.id)
            if previous:
                owned.remove(previous.id)
        for item in list(self.state.gear.values()):
            if item.id not in owned and self.budget >= 2:
                self.tick(2)
                if equipment.smelt_gear(self.state, item.id, self.gear_rules):
                    raise RuntimeError("模拟熔炼校验失败")
        # 先补齐六名主力，再支付突破声望；等级和强化均均匀培养。
        for _ in range(120):
            changed = False
            for disciple in sorted(self.state.disciples, key=lambda value: (value.level, value.id)):
                if self.budget < 3:
                    break
                costs, error = progression.can_breakthrough(self.state, disciple, self.templates[disciple.template_id])
                if len(self.party()) == 6 and error is None:
                    self.tick(3)
                    progression.breakthrough(self.state, disciple.id, self.templates)
                    self.ledger["breakthroughs"] += 1
                    changed = True
                if progression.can_upgrade(self.state, disciple) is None:
                    self.tick(3)
                    progression.upgrade(self.state, disciple.id)
                    self.ledger["level_ups"] += 1
                    changed = True
            if not changed:
                break
        for _ in range(30):
            changed = False
            items = [self.state.gear[key] for key in owned]
            for item in sorted(items, key=lambda value: (value.level, value.id)):
                if self.budget < 3:
                    break
                cost = equipment.upgrade_costs(item, self.gear_rules)
                if item.level >= self.state.facility_levels.get("forge", 1) * self.gear_rules["levels_per_forge"]:
                    continue
                if any(self.state.inventory.get(key, 0) < value for key, value in cost.items()):
                    continue
                self.tick(3)
                if equipment.upgrade_gear(self.state, item.id, self.gear_rules):
                    raise RuntimeError("模拟强化校验失败")
                self.ledger["gear_upgrades"] += 1
                changed = True
            if not changed:
                break
        for identity in ("hall", "forge", "training", "tower", "alchemy"):
            while self.budget >= 5:
                view = next(item for item in facility_views(self.state, self.facilities) if item.id == identity)
                if view.reason:
                    break
                self.tick(5)
                if upgrade_facility(self.state, identity, self.facilities):
                    raise RuntimeError("模拟设施升级校验失败")
                conquest.ensure_sects(self.state, load_sects(), self.enemies, self.world)
        if any(disciple.injury_stacks for disciple in self.state.disciples) and self.budget >= 5:
            preview = heal_party_preview(self.state, self.party(), self.recipes)
            if preview["healed"]:
                self.tick(5)
                heal_party(self.state, self.party(), self.recipes)
        # 杜甫在本宗恢复行动力，其余优先驻守已攻克资源点；出征引擎负责离岗回岗。
        conquered = [sect for sect in self.state.sects if sect.conquered]
        for disciple in self.state.disciples:
            if disciple.id == "dufu" or not conquered:
                if not any(slot.disciple_id == disciple.id for slot in self.state.duty_slots):
                    duty.assign(self.state, disciple.id, self.templates, self.now, self.bonds)
            elif not any(slot.disciple_id == disciple.id for sect in conquered for slot in sect.garrison):
                target = next((sect for sect in conquered if len(sect.garrison) < 3), None)
                if target:
                    assign_garrison(self.state, target.id, disciple.id, self.now)
        duty.record_event(self.state, self.templates, self.now, self.bonds)
        equipped = sum(len(disciple.gear_slots) for disciple in self.state.disciples)
        if equipped == 24 and self.first_24_slots is None:
            self.first_24_slots = self.elapsed()

    def party_fingerprint(self):
        # 失败记住出发前的完整可见培养与配装；治疗、护盾等不计入参考战力的属性也参与。
        party = self.state.disciples[:6]
        equipped = {key for disciple in party for key in disciple.gear_slots.values()}
        payload = {
            "disciples": [disciple.model_dump(exclude={"exp", "pill_uses", "pill_grades", "injured_until", "busy"}) for disciple in party],
            "gear": {key: self.state.gear[key].model_dump(exclude={"invested", "locked", "pending_affix"}) for key in sorted(equipped)},
            "bonuses": self.state.bonuses,
            "weapon_levels": {key: self.state.weapon_levels.get(key, 1) for disciple in party for key in disciple.equipment},
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def eligible(self, identity):
        return (identity not in self.attempted_this_session
                and self.party_fingerprint() not in self.failed_inputs.get(identity, set()))

    def dungeon_target(self):
        available = [item for item in world.world_view(self.state, self.world).regions[0].nodes
                     if item.kind == "dungeon" and not item.locked and self.eligible(item.id)]
        if not available:
            return None
        counts = Counter(slot for disciple in self.state.disciples for slot in disciple.gear_slots)
        missing = [item for item in available if item.gear_slot and counts[item.gear_slot] < len(self.party())]
        if missing:
            return min(missing, key=lambda item: (counts[item.gear_slot], -item.area, item.id))
        quality = {
            slot: sum(self.state.gear[disciple.gear_slots[slot]].level
                      + self.state.gear[disciple.gear_slots[slot]].affix_grade / 3
                      for disciple in self.state.disciples if slot in disciple.gear_slots) / max(1, counts[slot])
            for slot in equipment.SLOTS
        }
        # 补齐后优先已开放高收益片区；同片区再照顾强化/词条较弱部位，失败输入不变则回退。
        return min(available, key=lambda item: (-item.area, quality.get(item.gear_slot, min(quality.values())), item.id))

    def target(self):
        state = self.state
        tower_cost = self.modes["tower"]["stamina_cost"]
        reserve = 2 if not self.policy["tower_first"] and len(self.party()) == 6 and not self.dungeons_in_session else 0
        if state.world.pending_invasions["1"] and self.eligible("r1:raid"):
            return "r1:raid", None
        if self.policy["tower_first"] and self.towers_in_session == 0 and state.resources.stamina >= tower_cost:
            return "legacy_tower", None
        for area in range(1, 4):
            for kind in ("gate", "invasion"):
                identity = f"r1:{kind}:{area}"
                if identity in state.world.cleared_nodes or not self.eligible(identity):
                    continue
                node, error = world.prepare_world_node(state, identity, self.world)
                if error is None and state.resources.stamina >= node["stamina_cost"] + (reserve if node["stamina_cost"] else 0):
                    return identity, None
        if len(self.party()) < 6 and state.resources.stamina >= tower_cost:
            return "legacy_tower", None
        for sect in state.sects:
            if not sect.conquered and sect.area <= state.world.unlocked_areas["1"] and self.eligible(sect.id) and state.resources.stamina >= 2 + reserve:
                return "sect", sect
        if state.resources.stamina >= (tower_cost if self.policy["tower_first"] else 2):
            if self.policy["tower_first"]:
                return "legacy_tower", None
            target = self.dungeon_target()
            if target:
                return target.id, None
        return None, None

    def play_run(self, identity, sect, practice=False, seed_override=None):
        before_stamina = self.state.resources.stamina
        before_gear = self.state.next_gear_id
        mode = deepcopy(self.modes["expedition"]) if sect else world.tower_mode(self.state, self.modes["tower"], self.world)
        node = None
        if identity not in {"legacy_tower", "sect"}:
            node, error = world.prepare_world_node(self.state, identity, self.world, practice=practice)
            if error:
                raise RuntimeError(error)
            mode.update(node["mode_overrides"])
            mode.update(id="tower" if node["kind"] == "tower" else "dungeon" if node["kind"] == "dungeon" else "world",
                        world_node=node, gear_tier=node["gear_tier"], gear_slot=node["gear_slot"],
                        opportunities=node["kind"] == "dungeon")
        seed = self.scheduler.next_u32() if seed_override is None else seed_override
        score = self.score()
        fingerprint = self.party_fingerprint()
        error = run_engine.start_run(
            self.state, self.party(), self.templates, mode, self.now, seed=seed,
            bonds=self.bonds, skills=self.skills, enemies=self.enemies,
            affix_pool=self.affixes if not sect and (not node or node["kind"] == "dungeon") else [],
            weapons=self.weapons, route_version=2, sect=sect,
        )
        if error:
            raise RuntimeError(error)
        if node:
            self.state.active_run.world_node_id = node["id"]
            self.state.active_run.practice = practice
        self.ledger["stamina_spent"] += before_stamina - self.state.resources.stamina
        duty.record_event(self.state, self.templates, self.now, self.bonds)
        battles = choices = 0
        while run_engine.run_status(self.state.active_run) not in {"cleared", "defeated"}:
            run = self.state.active_run
            if sect:
                alive = [key for key in run.party if run.member_hp.get(key, 0) > 0]
                chosen = sorted(alive, key=lambda key: run.member_hp[key], reverse=True)[:3]
                error = conquest.arena(self.state, chosen)
                battles += 1
                self.tick(30)
            elif run.affix_pending:
                # 固定取第一个可见候选，避免读取未来随机结果挑最优局。
                error = run_engine.pick_affix(self.state, run.affix_options[0])
                choices += 1
                self.tick(5)
            else:
                chosen = min(range(len(run.choices)), key=lambda index: run.choices[index].power)
                opportunity = run.choices[chosen].kind in {"rest", "event"}
                error = run_engine.choose(self.state, chosen)
                battles += int(not opportunity)
                choices += 1
                self.tick(10 if opportunity else 30)
            if error:
                raise RuntimeError(error)
        run = self.state.active_run
        event = {"target": sect.id if sect else identity, "run_seed": seed, "hours": self.elapsed(),
                 "party": list(run.party), "power_reference": round(score, 2), "battles": battles,
                 "cleared_nodes": len(run.nodes), "drops": self.state.next_gear_id - before_gear,
                 "rounds": run.last_battle.rounds if run.last_battle else 0,
                 "reason": run.last_battle.reason if run.last_battle else "", "practice": practice}
        if run.last_battle:
            final_units = run.last_battle.final_units
            event["allies_survived"] = sum(unit.side == "ally" and unit.hp > 0 for unit in final_units)
            event["ally_remaining_hp"] = sum(unit.hp for unit in final_units if unit.side == "ally")
            event["enemy_remaining_hp"] = sum(unit.hp for unit in final_units if unit.side == "enemy")
        result = run_engine.settle_run(self.state, {}, self.now)
        duty.record_event(self.state, self.templates, self.now, self.bonds)
        event.update(victory=result["victory"], loot=result["loot"])
        event["retained_drops"] = len(result["gear"])
        self.ledger["retained_drops"] += len(result["gear"])
        for item in result["gear"]:
            self.ledger[f"affix_grade_{item.affix_grade}"] += 1
        self.runs.append(event)
        self.ledger["battles"] += battles
        self.ledger["runs"] += 1
        self.ledger["drops"] += event["drops"]
        for key, value in result["loot"].items():
            self.ledger[f"{identity.split(':')[1] if ':' in identity else identity}_{key}"] += value
        if not result["victory"]:
            failed = sect.id if sect else identity
            self.attempted_this_session.add(failed)
            if not practice:
                self.failed_inputs.setdefault(failed, set()).add(fingerprint)
        if identity == "legacy_tower":
            self.towers_in_session += 1
        if node and node["kind"] == "dungeon" and not practice:
            self.dungeons_in_session += 1
        if self.state.inventory.get(self.world["ascension_token"], 0) and self.first_token is None:
            self.first_token = {"hours": self.elapsed(), "day": int(self.elapsed() // 24) + 1,
                                "party": list(self.party()), "levels": [d.level for d in self.state.disciples],
                                "realms": [d.realm for d in self.state.disciples],
                                "equipped_slots": sum(len(d.gear_slots) for d in self.state.disciples),
                                "stamina_spent": round(self.ledger["stamina_spent"], 3), "runs": len(self.runs),
                                "ledger_at_clear": {key: round(value, 4) for key, value in self.ledger.items()}}
            self.first_clear_state = deepcopy(self.state)

    def equipment_comparison(self, day7=False):
        source = deepcopy(self.day7_state if day7 else self.first_clear_state or self.state)
        candidates = [node for node in world.world_view(source, self.world).regions[0].nodes
                      if node.kind in {"gate", "invasion"} and not node.locked]
        target = "r1:invasion:3" if any(node.id == "r1:invasion:3" for node in candidates) else next((node.id for node in candidates if not node.cleared), candidates[-1].id)
        healing = heal_party(source, [disciple.id for disciple in source.disciples], self.recipes)
        results = []
        battle_seed = self.seed * 1009 + 314159
        for variant in ("actual_equipment", "naked", "all_affixes_lowest_grade"):
            trial = Simulation(self.seed, self.scenario, self.profile)
            trial.state = deepcopy(source)
            trial.now = trial.last_settled = self.now
            trial.budget = 3600
            if variant == "naked":
                for disciple in trial.state.disciples:
                    disciple.gear_slots = {}
                    disciple.equipment = []
            elif variant == "all_affixes_lowest_grade":
                for item in trial.state.gear.values():
                    item.affix_grade = 1
                    item.affix_value = round(self.gear_rules["affix_grades"][0] * (1 + (item.tier - 1) * self.gear_rules["tier_growth"]), 6)
            trial.play_run(target, None, practice=True, seed_override=battle_seed)
            event = trial.runs[-1]
            results.append({key: event[key] for key in (
                "run_seed", "victory", "rounds", "reason", "allies_survived", "ally_remaining_hp", "enemy_remaining_hp",
            )} | {"variant": variant})
        return {"target": target, "source": "day7" if day7 else "first_token" if self.first_clear_state else "last_day",
                "levels": [disciple.level for disciple in source.disciples],
                "realms": [disciple.realm for disciple in source.disciples],
                "healed_with_real_stock": healing["healed"], "results": results}

    def simulate(self, days: int):
        for day in range(days):
            ledger_before = self.ledger.copy()
            for session in range(self.policy["sessions"]):
                scheduled = START + timedelta(days=day, hours=12 * session)
                self.tick(target=scheduled)
                self.budget = self.policy["minutes"] * 60 / self.policy["sessions"]
                self.towers_in_session = 0
                self.dungeons_in_session = 0
                self.attempted_this_session.clear()
                self.prepare_party()
                while self.budget >= 30:
                    identity, sect = self.target()
                    if identity is None:
                        break
                    self.play_run(identity, sect)
                    self.prepare_party()
            change = self.ledger - ledger_before
            self.daily.append({
                "day": day + 1, "hours": self.elapsed(), "disciples": len(self.party()),
                "levels": [d.level for d in self.state.disciples], "realms": [d.realm for d in self.state.disciples],
                "equipped_slots": sum(len(d.gear_slots) for d in self.state.disciples),
                "gear_levels": sorted(item.level for item in self.state.gear.values()),
                "unlocked_area": self.state.world.unlocked_areas["1"],
                "conquered_sects": sum(sect.conquered for sect in self.state.sects),
                "stamina_remaining": round(self.state.resources.stamina, 4),
                "stamina_recovered": round(change["stamina_recovered"], 4),
                "stamina_spent": round(change["stamina_spent"], 4),
                "battles": change["battles"], "drops": change["drops"],
                "active_minutes_estimate": round(change["active_seconds_estimate"] / 60, 2),
                "resources": self.state.resources.model_dump(),
                "gear_material": self.state.inventory.get("lian_qi_jing_cui", 0),
            })
            if day == 6:
                self.day7_state = deepcopy(self.state)
        probes = []
        if self.first_token is None:
            for node in world.world_view(self.state, self.world).regions[0].nodes:
                if node.kind not in {"gate", "invasion"} or node.locked or node.cleared:
                    continue
                trial = Simulation(self.seed, self.scenario, self.profile)
                trial.state = deepcopy(self.state)
                trial.now = trial.last_settled = self.now
                trial.budget = 3600
                healing = heal_party(trial.state, trial.party(), trial.recipes)
                trial.play_run(node.id, None, practice=True)
                probes.append({"target": node.id, "victory": trial.runs[-1]["victory"],
                               "rounds": trial.runs[-1]["rounds"], "reason": trial.runs[-1]["reason"],
                               "healed_with_real_stock": healing["healed"],
                               "injury_stacks": [disciple.injury_stacks for disciple in trial.state.disciples]})
        milestones = {"area1_hours": 0}
        for area in (2, 3):
            milestones[f"area{area}_hours"] = next((event["hours"] for event in self.runs
                                                    if event["target"] == f"r1:gate:{area - 1}" and event["victory"]), None)
        return {"seed": self.seed, "scenario": self.scenario, "profile": self.profile, "first_token": self.first_token,
                "milestones": milestones, "direct_final_team_probes": probes,
                "equipment_comparison": self.equipment_comparison(),
                "day7_equipment_comparison": self.equipment_comparison(day7=True) if self.day7_state else None,
                "first_six_hours": self.first_six, "first_24_slots_hours": self.first_24_slots,
                "recruited": self.recruited, "daily": self.daily,
                "ledger": {key: round(value, 4) for key, value in self.ledger.items()}, "runs": self.runs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", default="1,7,19,41,71,103,211,997")
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--scenarios", default=",".join(SCENARIOS))
    parser.add_argument("--profiles", default="formal", choices=["formal"])
    parser.add_argument("--compact", action="store_true", help="省略逐局轨迹，仅保存每日与里程碑证据")
    parser.add_argument("--summary-only", action="store_true", help="仅保存首周日指标和主要资源，不保留逐局轨迹")
    parser.add_argument("--output", default="artifacts/progression/baseline.json")
    args = parser.parse_args()
    seeds = [int(value) for value in args.seeds.split(",")]
    scenarios = args.scenarios.split(",")
    profiles = args.profiles.split(",")
    results = []
    for profile in profiles:
        for scenario in scenarios:
            for seed in seeds:
                result = Simulation(seed, scenario, profile).simulate(args.days)
                if args.compact or args.summary_only:
                    result.pop("runs")
                if args.summary_only:
                    seventh = result["daily"][min(6, len(result["daily"]) - 1)]
                    result["day7_resources"] = seventh["resources"]
                    result["day7_gear_levels"] = seventh["gear_levels"]
                    result["daily"] = [{key: day[key] for key in (
                        "day", "disciples", "equipped_slots", "stamina_recovered", "stamina_spent",
                        "battles", "drops", "active_minutes_estimate", "unlocked_area", "levels", "realms",
                    )} for day in result["daily"]]
                results.append(result)
            print(f"[progression] finished {profile} / {scenario}", flush=True)
    files = [path for path in (ROOT / "config").rglob("*.json") if not any(part in {"assets", "ui", "style"} for part in path.parts)]
    checksum = hashlib.sha256()
    for path in sorted(files):
        checksum.update(path.relative_to(ROOT).as_posix().encode())
        checksum.update(path.read_bytes())
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "config_sha256": checksum.hexdigest(),
               "policy_version": "visible_growth_retry_and_dungeon_budget_v4",
               "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "reproduce_command": "backend/.venv/Scripts/python.exe tools/simulate_world_progression.py " + " ".join(sys.argv[1:]),
               "assumptions": {"initial_reputation": 500, "initial_stamina": 3, "roster_order": ROSTER,
                               "scenarios": SCENARIOS, "profiles": {key: PROFILES[key] for key in profiles},
                               "battle_seconds_estimate": 30,
                               "growth_action_seconds_estimate": 3, "affix_choice_seconds_estimate": 5,
                               "notes": ["真实领域规则；不访问数据库和用户存档", "时长是操作预算假设，不是体验验收",
                                         "每次出征完整结算，预算允许最后一局超时；不在出征中强制中断",
                                         "只模拟首地区成长；领取令牌后仍留在首区以观察24槽积累",
                                         "地图策略每次登录为秘境保留2行动力；失败目标完整培养/装备输入变化后再试",
                                         "缺槽先刷定向部位，齐装后优先已开放最高片区；已知失败输入不变时回退",
                                         "固定可见信息策略，不窥探未来结果；较差掉落取多种子实际低位样本"]},
               "results": results}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for profile in profiles:
        for scenario in scenarios:
            samples = [item for item in results if item["scenario"] == scenario and item["profile"] == profile]
            token_days = [item["first_token"]["day"] for item in samples if item["first_token"]]
            day7_slots = [item["daily"][min(6, len(item["daily"]) - 1)]["equipped_slots"] for item in samples]
            print(json.dumps({"profile": profile, "scenario": scenario, "samples": len(samples), "token_clear_count": len(token_days),
                              "token_day_min": min(token_days, default=None), "token_day_max": max(token_days, default=None),
                              "day7_slots_min": min(day7_slots), "day7_slots_max": max(day7_slots)}, ensure_ascii=False))
    print(f"[progression] evidence: {output}")


if __name__ == "__main__":
    main()
