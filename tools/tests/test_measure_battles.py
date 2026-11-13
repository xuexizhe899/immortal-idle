"""T17 测量工具的真实风险检查。

覆盖策略只使用可见选项、投入费用复用真实规则、战报统计、可复现性与 T16 对照。
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import measure_battles as measure  # noqa: E402
import compare_affix_choices as compare_affixes  # noqa: E402
from app.models.battle import BattleAction, BattleUnit, SkillDefinition  # noqa: E402
from app.models.save import BattleSummary, RunNode  # noqa: E402


class MeasureBattlesTests(unittest.TestCase):
    def test_battle_metrics_separate_ally_and_enemy_healing(self) -> None:
        battle = BattleSummary.model_validate({
            "id": "mixed-sides", "party_power": 0, "enemy_power": 0,
            "hp_before": 100, "hp_after": 100, "damage": 0, "won": True,
            "node": {"kind": "battle", "enemy": "enemy", "power": 0},
            "rounds": 1, "reason": "victory",
            "final_units": [
                {"id": unit_id, "template_id": unit_id, "name": unit_id,
                 "side": side, "slot": 0, "hp": 100, "max_hp": 100,
                 "attack": 10, "defense": 10, "speed": 10}
                for unit_id, side in (("enemy:ally-fixture", "ally"), ("foe", "enemy"))
            ],
            "events": [{
                "sequence": 1, "round": 1, "actor_id": "enemy:ally-fixture",
                "skill_id": "fixture", "skill_name": "测试", "vfx": "heal",
                "effects": [
                    {"target_id": target, "kind": kind, "amount": amount,
                     "absorbed": absorbed, "hp_after": 100, "shield_after": 0,
                     "source": "fixture"}
                    for target, kind, amount, absorbed in (
                        ("enemy:ally-fixture", "heal", 11, 0),
                        ("foe", "heal", 23, 0),
                        ("enemy:ally-fixture", "damage", 5, 7),
                        ("foe", "damage", 17, 13),
                    )
                ],
            }],
        })
        metrics = measure.battle_metrics(battle, 1)
        self.assertEqual(metrics["effective_healing"], 11)
        self.assertEqual(metrics["effective_healing_on_enemies"], 23)
        self.assertEqual(metrics["heal_effects"], 1)
        self.assertEqual(metrics["heal_effects_on_enemies"], 1)
        self.assertEqual(measure.summarize_encounters([metrics])["battle"]["effective_healing_on_enemies"], 23)

        state = compare_affixes.make_state(4, 2, compare_affixes.DEFAULT_PARTY)
        compare_affixes.start_run(
            state, compare_affixes.DEFAULT_PARTY, measure.load_disciples(),
            measure.load_modes()["tower"], compare_affixes.NOW, seed=11,
        )
        state.active_run.last_battle = battle
        with patch.object(compare_affixes, "run_status", side_effect=["choosing_node", "defeated"]), \
                patch.object(compare_affixes, "choose"):
            result = compare_affixes.finish(state)
        self.assertEqual(result["healed"], 11)
        self.assertEqual(result["enemy_healed"], 23)
        self.assertEqual(result["absorbed"], 7)
        self.assertEqual(result["enemy_absorbed"], 13)
        self.assertEqual(result["dealt"], 17)
        self.assertEqual(result["taken"], 5)
        self.assertEqual(result["termination"], "defeated")

    def test_affix_comparison_hp_scaling_keeps_fallen_members_at_zero(self) -> None:
        def advance_with_casualty(state, _step, _owned):
            run = state.active_run
            run.member_hp = {member: 100 for member in compare_affixes.DEFAULT_PARTY}
            run.member_hp[compare_affixes.DEFAULT_PARTY[0]] = 0
            run.affix_options = ["pan_shi"]

        observed = []
        with patch.object(compare_affixes, "advance", side_effect=advance_with_casualty), \
                patch.object(compare_affixes, "pick_affix"), \
                patch.object(compare_affixes, "finish", side_effect=lambda state: observed.append(state) or {}):
            compare_affixes.compare(11, 6, 4, 2, .25, [], compare_affixes.DEFAULT_PARTY)
        hp = observed[0].active_run.member_hp
        self.assertEqual(hp[compare_affixes.DEFAULT_PARTY[0]], 0)
        self.assertEqual(sum(hp.values()), 125)
        self.assertEqual(observed[0].active_run.hp, 125)

    def test_t17_matrix_shape(self) -> None:
        self.assertEqual(len(measure.LINEUPS), 6)
        self.assertEqual(len(measure.T17_TIERS), 4)
        self.assertEqual(len(measure.POLICIES), 3)
        self.assertEqual(
            len(measure.LINEUPS) * len(measure.T17_TIERS) * len(measure.POLICIES) * len(measure.SEEDS),
            216,
        )

    def test_policy_uses_only_visible_node_and_affix_options(self) -> None:
        choices = [
            RunNode(kind="elite", enemy="elite", power=1),
            RunNode(kind="battle", enemy="battle", power=1),
        ]
        self.assertEqual(measure.choose_node_index(choices, "first"), 0)
        self.assertEqual(measure.choose_node_index(choices, "defensive"), 1)
        self.assertEqual(measure.choose_node_index(choices, "aggressive"), 0)

        pool = [
            {"id": "feng", "group": "fengrui", "effects": [{"stat": "atk", "value": .05}]},
            {"id": "jian", "group": "jianshou", "effects": [{"stat": "def", "value": .05}]},
            {"id": "mou", "group": "qimou", "effects": [{"stat": "atk", "value": .03}]},
        ]
        options = ["feng", "mou", "jian"]
        self.assertEqual(measure.choose_affix_index(options, pool, "first"), 0)
        self.assertEqual(measure.choose_affix_index(options, pool, "defensive"), 2)
        self.assertEqual(measure.choose_affix_index(options, pool, "aggressive"), 0)

    def test_affix_policy_uses_effect_scores_within_real_single_group(self) -> None:
        """真实引擎只给同组候选，策略仍应能区分效果而不是永远选第一项。"""
        pool = measure.load_affixes()
        self.assertEqual(
            measure.choose_affix_index(["bu_dong", "gui_xi", "tie_bi"], pool, "defensive"), 1,
        )
        self.assertEqual(
            measure.choose_affix_index(["bu_dong", "gui_xi", "tie_bi"], pool, "aggressive"), 0,
        )
        self.assertEqual(
            measure.choose_affix_index(
                ["ji_feng", "lie_jia", "shi_ru_po_zhu"], pool, "aggressive",
            ), 2,
        )
        self.assertEqual(
            measure.choose_affix_index(
                ["ji_feng", "lie_jia", "shi_ru_po_zhu"], pool, "defensive",
            ), 0,
        )

    def test_investment_reuses_current_upgrade_and_realm_costs(self) -> None:
        templates = measure.load_disciples()
        investment = measure.investment_for(("guanyu",), 3, 2, templates)
        self.assertEqual(investment["recruit_reputation"], 220.0)
        self.assertEqual(investment["level_upgrade"], {"cultivation": 60.0, "spirit_stone": 30.0})
        self.assertEqual(investment["realm_upgrade_reputation"], 110.0)
        self.assertEqual(investment["ownership_and_growth_total_reputation"], 330.0)
        self.assertEqual(measure.level_investment(1), {"cultivation": 0.0, "spirit_stone": 0.0})

    def test_battle_metrics_extract_real_events(self) -> None:
        active = SkillDefinition(
            id="fixture-art", name="测试招式", type="active", cooldown=1,
            actions=[
                BattleAction(kind="damage", target="enemy_first", coefficient=.5),
                BattleAction(kind="heal", target="ally_lowest", coefficient=.5),
                BattleAction(kind="shield", target="ally_lowest", coefficient=.5),
            ],
        )
        passive = SkillDefinition(id="fixture-passive", name="测试被动", type="passive")
        enemy_active = SkillDefinition(
            id="enemy-art", name="敌方攻击", type="active", cooldown=1,
            actions=[BattleAction(kind="damage", target="enemy_first", coefficient=1)],
        )
        ally = BattleUnit(
            id="ally", template_id="ally", name="友", slot=0,
            attack=15, defense=2, health=100, speed=5,
            active=active, passive=passive,
        )
        enemy = BattleUnit(
            id="enemy", template_id="enemy", name="敌", slot=0,
            attack=10, defense=2, health=200, speed=10,
            active=enemy_active, passive=passive,
        )
        outcome = measure.simulate_battle([ally], [enemy], {})
        summary = BattleSummary(
            id="fixture", party_power=0, enemy_power=0,
            hp_before=100, hp_after=sum(unit.hp for unit in outcome.final_units if unit.side == "ally"),
            damage=0, won=outcome.won, node=RunNode(kind="battle", enemy="enemy", power=0),
            rounds=outcome.rounds, reason=outcome.reason,
            initial_units=outcome.initial_units, final_units=outcome.final_units,
            events=outcome.events,
        )

        metrics = measure.battle_metrics(summary, 1)

        self.assertGreater(metrics["damage_to_enemies"], 0)
        self.assertGreater(metrics["damage_to_allies"], 0)
        self.assertGreater(metrics["effective_healing"], 0)
        self.assertGreater(metrics["shield_to_allies"], 0)
        self.assertGreater(metrics["shield_absorbed_on_allies"], 0)
        self.assertEqual(
            metrics["survivors"],
            sum(1 for unit in outcome.final_units if unit.side == "ally" and unit.hp > 0),
        )
        self.assertEqual(metrics["party_size"], 1)
        self.assertIsNone(metrics["heal_overflow"])

    def test_campaign_is_reproducible_without_extra_rng(self) -> None:
        kwargs = {
            "lineup": "wuhu_benyue",
            "party": measure.LINEUPS["wuhu_benyue"],
            "level": 1,
            "seed": 17,
            "policy": "first",
            "realm": 1,
            "tier": "early_l1_r1",
            "detailed": True,
        }
        first = measure.measure_campaign(**kwargs)
        second = measure.measure_campaign(**kwargs)
        first.pop("wall_ms")
        second.pop("wall_ms")
        self.assertEqual(first, second)
        self.assertEqual(first["rng_cursor"], second["rng_cursor"])
        self.assertEqual(first["decisions"], second["decisions"])
        self.assertEqual(
            first["effective_healing_on_enemies"],
            sum(battle["effective_healing_on_enemies"] for battle in first["battles"]),
        )
        self.assertEqual(
            measure.summarize_cases([first])[0]["avg_effective_healing_on_enemies"],
            first["effective_healing_on_enemies"],
        )

    def test_t19_matrix_shape(self) -> None:
        self.assertEqual(len(measure.T19_TIERS), 3)
        self.assertEqual(len(measure.T19_LOADOUTS), 4)
        self.assertEqual(
            len(measure.LINEUPS) * len(measure.T19_TIERS) * len(measure.T19_LOADOUTS) * len(measure.SEEDS),
            216,
        )

    def test_loadout_investment_uses_real_pill_and_weapon_materials(self) -> None:
        weapons = measure.load_weapons()
        recipes = measure.load_recipes()
        investment = measure.loadout_investment(
            ("guanyu",), weapons, recipes, pills=True, weapons_equipped=True,
        )
        self.assertEqual(
            investment["pill_materials"],
            {"han_tie": 6, "jiao_gu": 3, "ling_cao": 9, "yun_mu": 3},
        )
        self.assertEqual(
            investment["weapon_materials"],
            {"han_tie": 4, "jiao_gu": 2, "xuan_jing": 1},
        )
        self.assertEqual(
            investment["total_materials"],
            {"han_tie": 10, "jiao_gu": 5, "ling_cao": 9, "xuan_jing": 1, "yun_mu": 3},
        )

    def test_t19_loadout_is_recorded_and_keeps_control_reproducible(self) -> None:
        base = {
            "lineup": "wuhu_benyue",
            "party": measure.LINEUPS["wuhu_benyue"],
            "level": 3,
            "seed": 17,
            "policy": "first",
            "realm": 1,
            "tier": "mid_l3_r1",
            "detailed": True,
        }
        control = measure.measure_campaign(**base)
        loaded = measure.measure_campaign(**base, pills=True, weapon_loadout=True)
        self.assertEqual(control["loadout"], {"pills": False, "weapons": False})
        self.assertEqual(loaded["loadout"], {"pills": True, "weapons": True})
        self.assertEqual(control["equipment_investment"]["total_materials"], {})
        self.assertTrue(loaded["equipment_investment"]["pill_materials"])
        self.assertTrue(loaded["equipment_investment"]["weapon_materials"])
        self.assertGreater(loaded["damage_to_enemies"], 0)

    def test_t18_reference_comparison_ignores_loaded_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t18.json"
            old_case = {
                "lineup": "fixture", "level": 3, "realm": 1, "policy": "first", "seed": 1,
                "tier": "mid_l3_r1", "termination": "cleared", "reached_floor": 20,
                "victory": True, "remaining_hp": 100, "remaining_hp_ratio": .5,
                "survivors": 6, "rounds_total": 10, "main_actions_total": 20,
                "effect_results_total": 30, "triggered_bonds": {}, "damage_to_enemies": 50,
                "damage_to_allies": 20, "effective_healing": 5,
                "shield_to_allies": 4, "shield_absorbed_on_allies": 3,
                "rng_cursor": 7, "decisions": [],
            }
            path.write_text(json.dumps({"input_sha256": "old", "cases": [old_case]}), encoding="utf-8")
            control = {**old_case, "loadout": {"pills": False, "weapons": False}}
            loaded = {**control, "loadout": {"pills": True, "weapons": True}, "remaining_hp": 1}
            reference = measure.compare_t18_reference([control, loaded], path)
            self.assertEqual(reference["matched_cases"], 1)
            self.assertEqual(reference["different_cases"], 0)

    def test_t20_matrix_shape(self) -> None:
        self.assertEqual(
            len(measure.LINEUPS) * len(measure.T18_TIERS) * len(measure.T19_LOADOUTS) * len(measure.SEEDS),
            288,
        )

    def test_compare_t19_reference_reports_aggregate_deltas(self) -> None:
        def case(termination: str, floor: int, hp: float, loadout: dict) -> dict:
            return {
                "lineup": "fixture", "tier": "mid_l3_r1", "seed": 1,
                "termination": termination, "reached_floor": floor,
                "remaining_hp_ratio": hp, "rounds_total": 10,
                "damage_to_enemies": 100, "damage_to_allies": 50,
                "effective_healing": 10, "survivors": 6,
                "loadout": loadout,
            }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t19.json"
            path.write_text(json.dumps({
                "input_sha256": "old",
                "cases": [
                    case("cleared", 20, .8, {"pills": False, "weapons": False}),
                    case("cleared", 20, .9, {"pills": True, "weapons": True}),
                ],
            }), encoding="utf-8")
            new_cases = [
                case("defeated", 17, .1, {"pills": False, "weapons": False}),
                case("cleared", 20, .6, {"pills": True, "weapons": True}),
            ]
            for new_case in new_cases:
                new_case["effective_healing_on_enemies"] = 7
            reference = measure.compare_t19_reference(new_cases, path)
            self.assertEqual(reference["compared_cases"], 2)
            self.assertEqual(reference["different_cases"], 2)
            self.assertEqual(len(reference["aggregate"]), 2)
            control = next(row for row in reference["aggregate"] if row["loadout"] == "control")
            self.assertEqual(control["old_clear_rate"], 1.0)
            self.assertEqual(control["new_clear_rate"], 0.0)
            self.assertEqual(control["delta_clear_rate"], -1.0)
            self.assertEqual(control["delta_avg_reached_floor"], -3.0)
            self.assertIsNone(control["old_avg_effective_healing"])
            self.assertIsNone(control["delta_avg_effective_healing"])
            self.assertIn("effective_healing", reference["unavailable_comparisons"])
            self.assertEqual(control["new_avg_effective_healing"], 10)
            self.assertEqual(control["new_avg_effective_healing_on_enemies"], 7)

            # 双方口径均有记录时，治疗差值才有可比含义。
            old_data = json.loads(path.read_text(encoding="utf-8"))
            for old_case in old_data["cases"]:
                old_case["effective_healing_on_enemies"] = 2
            path.write_text(json.dumps(old_data), encoding="utf-8")
            reference = measure.compare_t19_reference(new_cases, path)
            self.assertEqual(reference["unavailable_comparisons"], [])
            self.assertEqual(reference["aggregate"][0]["delta_avg_effective_healing_on_enemies"], 5)

    def test_loadout_name_is_stable(self) -> None:
        self.assertEqual(measure.loadout_name({"loadout": {"pills": False, "weapons": False}}), "control")
        self.assertEqual(measure.loadout_name({"loadout": {"pills": True, "weapons": False}}), "pills")
        self.assertEqual(measure.loadout_name({"loadout": {"pills": False, "weapons": True}}), "weapons")
        self.assertEqual(measure.loadout_name({"loadout": {"pills": True, "weapons": True}}), "both")

    def test_t16_reference_comparison_reports_changed_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t16.json"
            old_case = {
                "lineup": "fixture", "level": 1, "seed": 1,
                "reached_floor": 20, "won_battles": 20, "victory": True,
                "remaining_hp": 100, "rounds_total": 10, "main_actions_total": 20,
                "effect_results_total": 30, "triggered_bonds": {"bond": 1},
            }
            path.write_text(
                json.dumps({"input_sha256": "old", "campaigns": [old_case]}),
                encoding="utf-8",
            )
            new_case = {
                **old_case, "policy": "first", "realm": 1,
            }
            same = measure.compare_t16_reference([new_case], path)
            self.assertTrue(same["available"])
            self.assertEqual(same["matched_cases"], 1)
            self.assertEqual(same["different_cases"], 0)

            changed_case = {**new_case, "remaining_hp": 99}
            changed = measure.compare_t16_reference([changed_case], path)
            self.assertEqual(changed["different_cases"], 1)
            self.assertIn("remaining_hp", changed["differences"][0]["fields"])


if __name__ == "__main__":
    unittest.main()
