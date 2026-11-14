"""设施与培养回归：扣费原子性、旧效果补差及队伍补炼疗伤。"""

import pytest

from app.config_loader import load_facilities, load_recipes
from app.domain.craft import craft, recipe_view
from app.domain.facilities import upgrade_facility
from app.domain.items import heal_party, heal_party_preview, use_pill
from app.domain.weapons import battle_bonuses, combat_bonuses, upgrade_weapon
from app.models.save import DiscipleState, GameState, Resources


def test_batch_craft_uses_server_maximum_and_rejects_overspend():
    recipes = load_recipes()
    state = GameState(inventory={"ling_cao": 5, "yun_mu": 2})
    assert recipe_view(state, recipes["liao_shang_dan"]).max_quantity == 2
    before = state.model_dump()
    assert craft(state, "liao_shang_dan", recipes, quantity=3)
    assert state.model_dump() == before
    assert craft(state, "liao_shang_dan", recipes, quantity=2) is None
    assert state.inventory == {"ling_cao": 3, "liao_shang_dan": 2}
    assert craft(state, "liao_shang_dan", recipes, quantity=0)


def test_legacy_artifact_upgrade_only_adds_its_difference():
    state = GameState(
        crafted_recipes=["qing_feng_jian"], bonuses={"atk": .18},
        inventory={"han_tie": 20}, facility_levels={"forge": 3},
    )
    recipes = load_recipes()
    assert craft(state, "qing_feng_jian", recipes, grade=2) is None
    assert state.bonuses["atk"] == pytest.approx(.22)
    assert craft(state, "qing_feng_jian", recipes, grade=3) is None
    assert state.bonuses["atk"] == pytest.approx(.26)
    before = state.model_dump()
    assert craft(state, "qing_feng_jian", recipes, grade=3)
    assert state.model_dump() == before


def test_advanced_pills_replace_legacy_slots_without_regranting_old_effects():
    disciple = DiscipleState(id="d", template_id="t", pill_uses={"ju_qi_dan": 3}, bonuses={"atk": .15})
    state = GameState(disciples=[disciple], inventory={"ju_qi_dan:g2": 1, "ju_qi_dan:g3": 3})
    recipes = load_recipes()
    assert use_pill(state, "d", "ju_qi_dan:g2", recipes, {}) is None
    assert disciple.bonuses["atk"] == pytest.approx(.175)
    for _ in range(3):
        assert use_pill(state, "d", "ju_qi_dan:g3", recipes, {}) is None
    assert disciple.bonuses["atk"] == pytest.approx(.3)
    assert disciple.pill_uses["ju_qi_dan"] == 3
    assert disciple.pill_grades["ju_qi_dan"] == [3, 3, 3]
    state.inventory["ju_qi_dan:g2"] = 1
    before = state.model_dump()
    assert use_pill(state, "d", "ju_qi_dan:g2", recipes, {})
    assert state.model_dump() == before


def test_grade_locks_and_functional_pill_grade_do_not_spend():
    state = GameState(inventory={"ling_cao": 100, "jiao_gu": 10})
    before = state.model_dump()
    assert craft(state, "ju_qi_dan", load_recipes(), grade=2) == "请先升级炼丹房"
    assert craft(state, "liao_shang_dan", load_recipes(), grade=2)
    assert state.model_dump() == before
    state.facility_levels["alchemy"] = 2
    assert craft(state, "ju_qi_dan", load_recipes(), quantity=2, grade=2) is None
    assert state.inventory["ju_qi_dan:g2"] == 2


def test_healing_uses_old_stock_then_only_missing_materials_and_prioritizes_injuries():
    state = GameState(
        disciples=[
            DiscipleState(id="light", template_id="t", injury_stacks=1),
            DiscipleState(id="heavy1", template_id="t", injury_stacks=3),
            DiscipleState(id="heavy2", template_id="t", injury_stacks=3),
        ],
        inventory={"healing_pill": 1, "ling_cao": 8, "yun_mu": 1},
    )
    party = ["light", "heavy2", "heavy1"]
    preview = heal_party_preview(state, party, load_recipes())
    assert preview["healed"] == ["heavy2", "heavy1"]
    assert preview["stock_used"] == preview["crafted"] == 1
    assert preview["costs"] == {"ling_cao": 1, "yun_mu": 1}
    assert all(d.injury_stacks for d in state.disciples)
    assert heal_party(state, party, load_recipes()) == preview
    assert [d.injury_stacks for d in state.disciples] == [1, 0, 0]
    assert state.inventory == {"ling_cao": 7}


def test_healing_does_not_craft_when_stock_suffices_or_invalid_party():
    state = GameState(
        disciples=[DiscipleState(id="d", template_id="t", injury_stacks=2)],
        inventory={"liao_shang_dan": 5, "ling_cao": 8, "yun_mu": 8},
    )
    before = state.model_dump()
    assert heal_party(state, ["d", "d"], load_recipes())["reason"]
    assert state.model_dump() == before
    result = heal_party(state, ["d"], load_recipes())
    assert result["crafted"] == 0
    assert state.inventory == {"liao_shang_dan": 4, "ling_cao": 8, "yun_mu": 8}


def test_facility_upgrade_respects_hall_cap_and_atomic_costs():
    state = GameState(resources=Resources(spirit_stone=100), inventory={"chi_tong": 10, "qing_shi": 10})
    before = state.model_dump()
    assert upgrade_facility(state, "forge", load_facilities()) == "请先升级宗门主殿"
    assert state.model_dump() == before
    state.facility_levels["hall"] = 2
    assert upgrade_facility(state, "forge", load_facilities()) is None
    assert state.facility_levels["forge"] == 2
    assert state.resources.spirit_stone == 88
    assert state.inventory == {"chi_tong": 4, "qing_shi": 6}


def test_equipped_weapon_level_follows_weapon_and_does_not_pollute_personal_bonus():
    weapons = {"w": {"id": "w", "stats": {"atk": .1, "damage": .05}, "inputs": {"han_tie": 2}}}
    disciple = DiscipleState(id="d", template_id="t", equipment=["w"])
    state = GameState(
        disciples=[disciple], facility_levels={"forge": 2},
        inventory={"han_tie": 4, "gong_fa_qi_pei": 1},
    )
    assert upgrade_weapon(state, "w", weapons) is None
    assert state.weapon_levels == {"w": 2}
    assert disciple.bonuses == {}
    assert combat_bonuses(disciple, {}, weapons, state.weapon_levels)["atk"] == pytest.approx(.15)
    assert battle_bonuses(disciple, weapons, state.weapon_levels)["damage"] == pytest.approx(.075)
    before = state.model_dump()
    assert upgrade_weapon(state, "w", weapons) == "请先升级炼器炉"
    assert state.model_dump() == before


def test_training_preview_matches_personal_production_with_specialty_and_facility():
    from app.config_loader import load_disciples, load_skills, load_weapons
    from app.domain.duty import personal_duty_rates
    from app.domain.training import preview

    templates = load_disciples()
    disciple = DiscipleState(id="h", template_id="huatuo", level=3)
    state = GameState(
        disciples=[disciple, DiscipleState(id="other", template_id="zhangheng")],
        facility_levels={"training": 3}, bonuses={"material_rate": 4},
    )
    before = state.model_dump()
    result = preview(state, disciple, templates["huatuo"], load_skills(), load_weapons())
    expected = personal_duty_rates(disciple, templates["huatuo"], 3)
    assert result.current.duty_rates == pytest.approx(expected)
    assert result.current.duty_rates["material_ling_cao_flat"] == pytest.approx(.75)
    assert result.current.duty_rates["material_rate"] == pytest.approx(.105)
    assert result.next_realm.target.duty_rates["material_rate"] == pytest.approx(.12)
    assert state.model_dump() == before
