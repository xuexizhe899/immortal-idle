"""T22 测量器：可见政策、重复分母、真实结算与分支隔离。"""

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import measure_routes as measure  # noqa: E402


def test_policies_use_visible_fields_and_stable_ties():
    options = [
        {"power": 20, "reward": {"cultivation": 10}},
        {"power": 12, "reward": {"cultivation": 20}},
        {"power": 12, "reward": {"cultivation": 20}},
    ]
    assert measure.select_route(options, "first") == 0
    assert measure.select_route(options, "low_power") == 1
    assert measure.select_route(options, "high_reward") == 1


def test_duplicate_statistics_exclude_single_routes_and_preserve_enemy_order():
    option = {"kind": "battle", "enemy": "display-a", "enemies": ["front", "back"], "power": 50, "reward": {"cultivation": 10}}
    display_variant = {**option, "enemy": "display-b"}
    reversed_slots = {**option, "enemies": ["back", "front"]}
    decisions = [
        {"type": "node", "options": [option, display_variant]},
        {"type": "node", "options": [option, reversed_slots]},
        {"type": "node", "options": [option]},
        {"type": "node", "options": [{**option, "kind": "boss"}]},
        {"type": "affix", "options": ["first", "second"]},
    ]
    stats = measure.choice_statistics(decisions)
    assert stats["multiple_non_boss"] == 2
    assert stats["single_non_boss"] == 1
    assert stats["boss_decisions"] == 1
    assert stats["duplicate_decisions"] == 1
    assert stats["duplicate_rate_among_multiple"] == .5
    assert measure.choice_statistics(decisions[2:])["duplicate_rate_among_multiple"] is None


def test_campaign_replays_from_version_start_and_counts_real_commands():
    first = measure.measure_campaign("wuhu_benyue", "late_l6_r2", 17, 2, "low_power")
    repeated = measure.measure_campaign("wuhu_benyue", "late_l6_r2", 17, 2, "low_power")
    assert first == repeated
    assert first["initial_run"]["party_snapshot"]["route_version"] == 2
    assert first["command_total"] == sum(first["commands"].values())
    assert first["commands"]["choose"] == len(first["battles"])
    assert first["commands"]["affix"] == sum(row["type"] == "affix" for row in first["decisions"])
    assert first["commands"]["start"] == first["commands"]["settle"] == 1
    assert first["choice_statistics"]["duplicate_decisions"] == 0
    if first["termination"] == "cleared":
        assert first["command_total"] == 41
        for key in ("cultivation", "spirit_stone", "reputation"):
            assert first["settled_loot"][key] == first["pending_loot"][key]
    node_decisions = [row for row in first["decisions"] if row["type"] == "node"]
    for decision, battle in zip(node_decisions, first["battles"]):
        chosen = decision["options"][decision["chosen_index"]]
        assert chosen["enemies"] == battle["actual_enemies"]
        assert chosen["power"] == battle["actual_power"]
        assert battle["loot"] == (chosen["reward"] if battle["won"] else {})

    legacy = measure.measure_campaign("wuhu_benyue", "late_l6_r2", 17, 1, "low_power")
    assert legacy["initial_run"]["party_snapshot"]["route_version"] == 1
    assert legacy["choice_statistics"]["duplicate_decisions"] > 0


def test_fork_executes_actual_choices_without_mutating_natural_state():
    captured = []
    measure.measure_campaign("wuhu_benyue", "late_l6_r2", 17, 2, "low_power", captured)
    assert captured
    source = captured[0]
    before = source["state"].model_dump_json()
    result = measure.fork_choices(source)
    assert source["state"].model_dump_json() == before
    assert len(result["outcomes"]) == len(source["state"].active_run.choices)
    for outcome in result["outcomes"]:
        assert outcome["hp_after"] == sum(outcome["member_hp_after"].values())
        assert outcome["survivors"] == sum(hp > 0 for hp in outcome["member_hp_after"].values())
        assert outcome["loot"] == (outcome["option"]["reward"] if outcome["won"] else {})
        assert all(outcome["member_hp_after"][key] == 0 for key, hp in result["member_hp_before"].items() if hp == 0)


def test_summary_keeps_materials_and_counts_failure_settlement():
    cases = [
        {"route_version": 2, "policy": "first", "termination": "cleared", "reached_floor": 20,
         "command_total": 41, "decisions": [], "settled_loot": {"cultivation": 100, "han_tie": 7}},
        {"route_version": 2, "policy": "first", "termination": "defeated", "reached_floor": 5,
         "command_total": 11, "decisions": [], "settled_loot": {"cultivation": 20, "han_tie": 1}},
    ]
    summary = measure.summarize(cases)[0]
    assert summary["clears"] == 1
    assert summary["avg_commands"] == 26
    assert summary["settled_loot_total"] == {"cultivation": 120, "han_tie": 8}


def test_tradeoff_search_reports_missing_evidence_without_inventing_states():
    result = measure.find_tradeoffs([])
    assert result["examples"] == []
    assert result["missing_examples"] == 1
    assert result["evaluated_states"] == 0
