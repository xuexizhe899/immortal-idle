"""炼制测试：材料扣除、永久加成与特殊配方。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.craft import craft
from app.models.save import DiscipleState, GameState

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)

RECIPES = {
    "pill": {
        "id": "pill",
        "name": "聚气丹",
        "kind": "pill",
        "inputs": {"ling_cao": 2},
        "effects": [
            {"stat": "atk", "mode": "add_pct", "value": 0.05, "scope": "permanent"}
        ],
    },
    "heal_pill": {
        "id": "heal_pill",
        "name": "疗伤丹",
        "kind": "pill",
        "inputs": {"ling_cao": 1},
        "effects": [],
        "special": "heal",
    },
    "realm_pill": {
        "id": "realm_pill",
        "name": "破境丹",
        "kind": "pill",
        "inputs": {"xuan_jing": 1},
        "effects": [],
        "special": "realm",
    },
}


def make_state(**inventory: int) -> GameState:
    """构造带材料与一名受伤弟子的存档。"""
    return GameState(
        inventory=dict(inventory),
        disciples=[
            DiscipleState(
                id="d1",
                template_id="t",
                injury_stacks=2,
                injured_until=NOW + timedelta(hours=8),
            )
        ],
    )


def test_craft_consumes_materials_and_adds_bonus() -> None:
    """炼制扣材料，永久加成记入 bonuses。"""
    state = make_state(ling_cao=3)

    assert craft(state, "pill", None, RECIPES) is None
    assert state.inventory["ling_cao"] == 1
    assert state.bonuses["atk"] == pytest.approx(0.05)


def test_craft_removes_empty_material_entry() -> None:
    """材料刚好用完时，库存里不留 0。"""
    state = make_state(ling_cao=2)

    craft(state, "pill", None, RECIPES)

    assert "ling_cao" not in state.inventory


def test_craft_rejects_missing_materials() -> None:
    """材料不足时不扣材料也不加成。"""
    state = make_state(ling_cao=1)

    assert "材料不足" in (craft(state, "pill", None, RECIPES) or "")
    assert state.inventory["ling_cao"] == 1
    assert state.bonuses == {}


def test_craft_rejects_unknown_recipe() -> None:
    """配方不存在直接报错。"""
    state = make_state(ling_cao=5)
    assert craft(state, "ghost", None, RECIPES) == "配方不存在"


def test_special_recipe_needs_target() -> None:
    """疗伤丹与破境丹必须指定弟子。"""
    state = make_state(ling_cao=2)
    assert craft(state, "heal_pill", None, RECIPES) == "该配方需要指定弟子"


def test_heal_pill_clears_injury() -> None:
    """疗伤丹清空伤势与到期时间。"""
    state = make_state(ling_cao=1)

    assert craft(state, "heal_pill", "d1", RECIPES) is None
    assert state.disciples[0].injury_stacks == 0
    assert state.disciples[0].injured_until is None


def test_realm_pill_raises_realm() -> None:
    """破境丹让指定弟子境界 +1。"""
    state = make_state(xuan_jing=1)

    assert craft(state, "realm_pill", "d1", RECIPES) is None
    assert state.disciples[0].realm == 2
