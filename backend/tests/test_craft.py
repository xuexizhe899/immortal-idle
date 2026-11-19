"""炼制测试：丹药入行囊，普通装备不再通过器方提供宗门加成。"""

from __future__ import annotations

from datetime import datetime, timezone

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
        "max_uses": 3,
    },
    "heal_pill": {
        "id": "heal_pill",
        "name": "疗伤丹",
        "kind": "pill",
        "inputs": {"ling_cao": 1},
        "effects": [],
        "special": "heal",
    },
    "artifact": {
        "id": "artifact",
        "name": "青锋剑",
        "kind": "artifact",
        "inputs": {"han_tie": 3},
        "effects": [
            {"stat": "atk", "mode": "add_pct", "value": 0.08, "scope": "permanent"}
        ],
    },
}


def make_state(**inventory: int) -> GameState:
    """构造带材料与一名弟子的存档。"""
    return GameState(
        inventory=dict(inventory),
        disciples=[DiscipleState(id="d1", template_id="t")],
    )


def test_pill_craft_stores_item_instead_of_consuming_it() -> None:
    """丹药炼成后进入行囊，不写宗门加成。"""
    state = make_state(ling_cao=3)

    assert craft(state, "pill", RECIPES) is None
    assert state.inventory["ling_cao"] == 1
    assert state.inventory["pill"] == 1
    assert state.bonuses == {}


def test_craft_removes_empty_material_entry() -> None:
    """材料刚好用完时，库存里不留 0。"""
    state = make_state(ling_cao=2)

    craft(state, "pill", RECIPES)

    assert "ling_cao" not in state.inventory


def test_craft_rejects_missing_materials() -> None:
    """材料不足时不扣材料也不产出。"""
    state = make_state(ling_cao=1)

    assert "材料不足" in (craft(state, "pill", RECIPES) or "")
    assert state.inventory["ling_cao"] == 1
    assert "pill" not in state.inventory


def test_craft_rejects_unknown_recipe() -> None:
    """配方不存在直接报错。"""
    state = make_state(ling_cao=5)
    assert craft(state, "ghost", RECIPES) == "配方不存在"


def test_artifact_craft_is_rejected_without_spending() -> None:
    """普通装备改由掉落取得，旧器方命令不扣材料或发全局加成。"""
    state = make_state(han_tie=3)
    before = state.model_dump()
    assert "副本与首领掉落" in craft(state, "artifact", RECIPES)
    assert state.model_dump() == before


def test_legacy_artifact_cannot_be_crafted_again() -> None:
    """已有旧器方记录也不能继续制造或升级全局器具。"""
    state = make_state(han_tie=6)
    state.crafted_recipes = ["artifact"]
    state.bonuses = {"atk": .08}
    before = state.model_dump()
    assert "副本与首领掉落" in craft(state, "artifact", RECIPES)
    assert state.model_dump() == before


def test_craft_is_locked_during_active_run() -> None:
    """出征进行中不能炼制；不消耗材料。"""
    state = make_state(ling_cao=3)
    state.active_run = _active_run()

    assert "出征" in (craft(state, "pill", RECIPES) or "")
    assert state.inventory["ling_cao"] == 3


def _active_run():
    from app.models.save import ActiveRun

    return ActiveRun(run_seed=1, started_at=NOW)
